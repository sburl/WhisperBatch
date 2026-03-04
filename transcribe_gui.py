#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
from pathlib import Path
import queue
import os
import time
import subprocess
import json

from whisper_batch_core import (
    SUPPORTED_EXTENSIONS,
    SUPPORTED_OUTPUT_FORMATS,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TASK_NAME,
    DEFAULT_MODEL_NAME,
    SUPPORTED_MODELS,
    MODEL_METADATA,
    get_model_cache_dir,
    is_model_cached,
    build_output_metadata_path,
    effective_include_timestamps as _core_effective_include_timestamps,
    format_timestamp_with_millis as _core_format_timestamp_with_millis,
    load_model as core_load_model,
    render_output_text as _core_render_output_text,
    render_srt as _core_render_srt,
    render_vtt as _core_render_vtt,
    result_to_json_payload as _core_result_to_json_payload,
    resolve_output_metadata_path,
    should_skip_output_due_to_metadata,
    transcribe_segments,
)
import platform
import sys

# --- Environment sanity checks for macOS/Torch ---------------------------------
# If running on Apple Silicon ensure a native arm64 build of PyTorch is present.
# x86-64 wheels executed via Rosetta crash with a misleading loader error.
# We intercept that scenario to display actionable instructions instead.

def _check_pytorch_arch():
    try:
        import torch  # noqa: F401 – we only need the import side-effects
    except OSError as exc:
        if "have instead 16" in str(exc) and platform.machine() == "arm64":
            sys.stderr.write(
                "\n🚫 Detected x86-64 PyTorch wheel running under Rosetta.\n"
                "Please reinstall the native arm64 wheel:\n\n"
                "    pip uninstall -y torch\n"
                "    pip install --no-cache-dir --force-reinstall torch==2.4.1 "
                "--index-url https://download.pytorch.org/whl/cpu\n\n"
                "Then run the program again.\n"
            )
            sys.exit(1)
    except ModuleNotFoundError:
        # torch not installed – setup is still in progress; skip check
        pass

_check_pytorch_arch()


def _format_timestamp_with_millis(seconds, separator=","):
    return _core_format_timestamp_with_millis(seconds, separator=separator)


def _render_srt(segments):
    return _core_render_srt(segments)


def _render_vtt(segments):
    return _core_render_vtt(segments)


def _result_to_json_payload(segments, include_timestamps: bool):
    return _core_result_to_json_payload(segments, include_timestamps=include_timestamps)


def _effective_include_timestamps_for_output(output_format: str, include_timestamps: bool):
    return _core_effective_include_timestamps(output_format, include_timestamps)


def _render_output_text(segments, output_format: str, include_timestamps: bool) -> str:
    return _core_render_output_text(
        segments,
        output_format=output_format,
        include_timestamps=include_timestamps,
    )

class TranscriptionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WhisperBatch")
        self.root.geometry("1000x800")
        
        # Create message queue for thread-safe updates
        self.queue = queue.Queue()
        
        # Control flags
        self.is_processing = False
        self.is_paused = False
        self.should_stop = False
        self.worker_thread = None
        
        # Task queue and progress tracking
        self.task_queue = queue.Queue()
        self.progress_lock = threading.Lock()
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        
        # Time tracking
        self.start_time = None
        self.total_elapsed_seconds = 0
        self.pause_start_time = None
        
        # Create main frame
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Create left and right frames
        self.left_frame = ttk.Frame(self.main_frame)
        self.left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Options frame
        self.options_frame = ttk.LabelFrame(self.left_frame, text="Options", padding="5")
        self.options_frame.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # Model selection
        ttk.Label(self.options_frame, text="Model:").grid(row=0, column=0, padx=5)
        self.model_var = tk.StringVar(
            value=(
                DEFAULT_MODEL_NAME
                if DEFAULT_MODEL_NAME in SUPPORTED_MODELS
                else SUPPORTED_MODELS[-1] if SUPPORTED_MODELS else DEFAULT_MODEL_NAME
            )
        )
        self.model_combo = ttk.Combobox(
            self.options_frame,
            textvariable=self.model_var,
            values=SUPPORTED_MODELS,
            state="readonly",
            width=10
        )
        self.model_combo.grid(row=0, column=1, padx=5)
        self.model_combo.bind('<<ComboboxSelected>>', self.on_model_change)
        
        # Default timestamps checkbox
        self.timestamps_var = tk.BooleanVar(value=True)
        self.timestamps_check = ttk.Checkbutton(
            self.options_frame,
            text="Default Timestamps",
            variable=self.timestamps_var
        )
        self.timestamps_check.grid(row=0, column=2, padx=5)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.overwrite_check = ttk.Checkbutton(
            self.options_frame,
            text="Overwrite outputs",
            variable=self.overwrite_var,
        )
        self.overwrite_check.grid(row=0, column=3, padx=5)
        self.resume_var = tk.BooleanVar(value=False)
        self.resume_check = ttk.Checkbutton(
            self.options_frame,
            text="Resume completed files",
            variable=self.resume_var,
        )
        self.resume_check.grid(row=0, column=4, padx=5)

        # Device selection
        ttk.Label(self.options_frame, text="Device:").grid(row=1, column=0, padx=5, pady=(5, 0))
        self.device_options = {
            "Auto (recommended)": "auto",
            "CPU": "cpu",
            "CUDA (NVIDIA GPU)": "cuda"
        }
        self.device_var = tk.StringVar(value="Auto (recommended)")
        self.device_combo = ttk.Combobox(
            self.options_frame,
            textvariable=self.device_var,
            values=list(self.device_options.keys()),
            state="readonly",
            width=18
        )
        self.device_combo.grid(row=1, column=1, padx=5, pady=(5, 0), sticky=tk.W)
        self.device_combo.bind('<<ComboboxSelected>>', self.on_device_change)

        # Compute type selection
        ttk.Label(self.options_frame, text="Compute:").grid(row=1, column=2, padx=5, pady=(5, 0))
        self.compute_label_to_type = {
            "Auto (recommended)": None,
            "Fast (float16)": "float16",
            "Balanced (int8_float16)": "int8_float16",
            "Memory Saver (int8)": "int8",
            "Precise (float32)": "float32"
        }
        self.compute_var = tk.StringVar(value="Auto (recommended)")
        self.compute_combo = ttk.Combobox(
            self.options_frame,
            textvariable=self.compute_var,
            values=[],
            state="readonly",
            width=22
        )
        self.compute_combo.grid(row=1, column=3, padx=5, pady=(5, 0), sticky=tk.W)
        self.compute_combo.bind('<<ComboboxSelected>>', self.on_compute_change)
        self.refresh_compute_options()

        # Output format selection
        ttk.Label(self.options_frame, text="Output:").grid(row=2, column=0, padx=5, pady=(5, 0))
        self.output_format_var = tk.StringVar(value=DEFAULT_OUTPUT_FORMAT)
        self.output_format_combo = ttk.Combobox(
            self.options_frame,
            textvariable=self.output_format_var,
            values=sorted(SUPPORTED_OUTPUT_FORMATS),
            state="readonly",
            width=8,
        )
        self.output_format_combo.grid(row=2, column=1, padx=5, pady=(5, 0), sticky=tk.W)
        
        # File selection button
        self.select_button = ttk.Button(
            self.left_frame, 
            text="Add Media Files",
            command=self.select_files
        )
        self.select_button.grid(row=1, column=0, pady=5, sticky=tk.W)
        self.select_folder_button = ttk.Button(
            self.left_frame,
            text="Add Folder",
            command=self.select_folder
        )
        self.select_folder_button.grid(row=1, column=1, pady=5, padx=(8, 0), sticky=tk.W)
        
        # File list frame
        self.file_list_frame = ttk.LabelFrame(self.left_frame, text="Files to Process", padding="5")
        self.file_list_frame.grid(row=2, column=0, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File list
        self.file_list = ttk.Treeview(
            self.file_list_frame,
            columns=("filename", "status", "timestamps", "model"),
            show="headings",
            height=10
        )
        self.file_list.heading("filename", text="Filename")
        self.file_list.heading("status", text="Status")
        self.file_list.heading("timestamps", text="Timestamps")
        self.file_list.heading("model", text="Model")
        self.file_list.column("filename", width=200)
        self.file_list.column("status", width=120)
        self.file_list.column("timestamps", width=100)
        self.file_list.column("model", width=100)
        self.file_list.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Enable drag and drop
        self.file_list.bind('<ButtonPress-1>', self.on_drag_start)
        self.file_list.bind('<B1-Motion>', self.on_drag_motion)
        self.file_list.bind('<ButtonRelease-1>', self.on_drag_release)
        
        # File list scrollbar
        self.file_list_scrollbar = ttk.Scrollbar(
            self.file_list_frame,
            orient=tk.VERTICAL,
            command=self.file_list.yview
        )
        self.file_list_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_list.configure(yscrollcommand=self.file_list_scrollbar.set)
        
        # File list buttons frame
        self.file_buttons_frame = ttk.Frame(self.file_list_frame)
        self.file_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        # File list control buttons
        self.remove_btn = ttk.Button(
            self.file_buttons_frame,
            text="Remove",
            command=self.remove_selected_file
        )
        self.remove_btn.grid(row=0, column=0, padx=2)
        
        self.toggle_timestamps_btn = ttk.Button(
            self.file_buttons_frame,
            text="Toggle Timestamps",
            command=self.toggle_selected_timestamps
        )
        self.toggle_timestamps_btn.grid(row=0, column=1, padx=2)
        
        self.change_model_btn = ttk.Button(
            self.file_buttons_frame,
            text="Change Model",
            command=self.change_selected_model
        )
        self.change_model_btn.grid(row=0, column=2, padx=2)
        
        # Control buttons frame
        self.control_frame = ttk.Frame(self.left_frame)
        self.control_frame.grid(row=3, column=0, pady=5)
        
        # Control buttons
        self.start_btn = ttk.Button(
            self.control_frame,
            text="Start",
            command=self.start_processing
        )
        self.start_btn.grid(row=0, column=0, padx=2)
        
        self.pause_btn = ttk.Button(
            self.control_frame,
            text="Pause",
            command=self.toggle_pause,
            state=tk.DISABLED
        )
        self.pause_btn.grid(row=0, column=1, padx=2)
        
        self.stop_btn = ttk.Button(
            self.control_frame,
            text="Stop",
            command=self.stop_processing,
            state=tk.DISABLED
        )
        self.stop_btn.grid(row=0, column=2, padx=2)
        
        # Elapsed time label near control buttons
        self.elapsed_time_label = ttk.Label(self.control_frame, text="Elapsed: 0s")
        self.elapsed_time_label.grid(row=0, column=3, padx=10)
        
        # Transcription text area
        self.text_area = scrolledtext.ScrolledText(
            self.right_frame,
            wrap=tk.WORD,
            width=80,
            height=30
        )
        self.text_area.grid(row=0, column=0, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status label
        self.status_label = ttk.Label(self.right_frame, text="Ready")
        self.status_label.grid(row=1, column=0, pady=5)
        self.metrics_label = ttk.Label(self.right_frame, text="Progress: 0/0 files, failed: 0")
        self.metrics_label.grid(row=2, column=0, pady=(0, 5))
        
        # Configure grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.left_frame.columnconfigure(0, weight=1)
        self.left_frame.rowconfigure(2, weight=1)
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=1)
        self.options_frame.columnconfigure(3, weight=1)
        self.file_list_frame.columnconfigure(0, weight=1)
        self.file_list_frame.rowconfigure(0, weight=1)
        
        # Start checking the queue
        self.check_queue()
        
        # Show model info
        self.show_model_info()

    def reset_progress_tracking(self):
        """Reset queue counters"""
        with self.progress_lock:
            self.total_tasks = 0
            self.completed_tasks = 0
            self.failed_tasks = 0
        self.metrics_label["text"] = "Progress: 0/0 files, failed: 0"

    def enqueue_task_from_values(self, item_id, values):
        """Push a pending file into the worker queue"""
        if len(values) < 5:
            return
        filename, status, timestamps_flag, file_model, file_path = values
        if status != "Pending":
            return
        include_timestamps = timestamps_flag == "Yes"
        file_path = os.path.abspath(file_path)
        with self.progress_lock:
            self.total_tasks += 1
        self.task_queue.put({
            "item_id": item_id,
            "filename": filename,
            "include_timestamps": include_timestamps,
            "file_path": file_path,
            "file_model": file_model,
            "output_format": self.output_format_var.get(),
            "overwrite": self.overwrite_var.get(),
            "resume": self.resume_var.get(),
        })

    def remove_selected_file(self):
        """Remove selected file from the queue"""
        selected = self.file_list.selection()
        if not selected:
            return
        
        for item in selected:
            self.file_list.delete(item)
        

    def toggle_selected_timestamps(self):
        """Toggle timestamps for selected file"""
        selected = self.file_list.selection()
        if not selected:
            return
        
        for item in selected:
            values = list(self.file_list.item(item)["values"])
            if len(values) >= 3:  # Ensure we have the timestamps value
                current = values[2]
                new_value = "No" if current == "Yes" else "Yes"
                values[2] = new_value
                self.file_list.item(item, values=values)

    def start_processing(self):
        """Start processing the file queue"""
        # If already processing but paused, just resume
        if self.is_processing and self.is_paused:
            self.is_paused = False
            self.start_time = time.time()
            self.select_button.configure(state=tk.DISABLED)
            self.select_folder_button.configure(state=tk.DISABLED)
            self.queue.put(("status", "Resuming..."))
            self.queue.put(("text", "\nResuming processing...\n"))
            return

        if not self.file_list.get_children() or self.is_processing:
            return
        
        # Fresh run
        self.is_processing = True
        self.should_stop = False
        self.is_paused = False
        self.total_elapsed_seconds = 0
        self.pause_start_time = None
        self.start_time = time.time()
        self.reset_progress_tracking()
        # Recreate the task queue for this run
        self.task_queue = queue.Queue()
        self.worker_initial_model = self.model_var.get()
        self.worker_device = self.get_selected_device()
        self.worker_compute_type = self.get_selected_compute_type()
        
        # Snapshot pending files on the main thread and enqueue them
        for item_id in self.file_list.get_children():
            values = self.file_list.item(item_id)["values"]
            self.enqueue_task_from_values(item_id, values)
        
        if self.total_tasks == 0:
            self.queue.put(("status", "No pending files to process"))
            self.is_processing = False
            self.start_btn.configure(state=tk.NORMAL)
            self.pause_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.DISABLED)
            self.select_button.configure(state=tk.NORMAL)
            self.select_folder_button.configure(state=tk.NORMAL)
            self.device_combo.configure(state="readonly")
            self.compute_combo.configure(state="readonly")
            self.output_format_combo.configure(state="readonly")
            return
        
        # Update button states
        self.start_btn.configure(state=tk.DISABLED)
        self.pause_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.NORMAL)
        self.select_button.configure(state=tk.DISABLED)
        self.select_folder_button.configure(state=tk.DISABLED)
        self.device_combo.configure(state=tk.DISABLED)
        self.compute_combo.configure(state=tk.DISABLED)
        self.output_format_combo.configure(state=tk.DISABLED)
        
        # Start the elapsed time updates
        self.update_remaining_time()
        
        # Start processing in a separate thread
        self.worker_thread = threading.Thread(target=self.process_queue)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def toggle_pause(self):
        """Toggle pause state"""
        self.is_paused = not self.is_paused
        self.pause_btn.configure(text="Resume" if self.is_paused else "Pause")
        
        if self.is_paused:
            # Pause - accumulate elapsed time
            if self.start_time:
                self.total_elapsed_seconds += int(time.time() - self.start_time)
                self.pause_start_time = time.time()
            # Enable file selection when paused
            self.select_button.configure(state=tk.NORMAL)
            self.select_folder_button.configure(state=tk.NORMAL)
            self.queue.put(("status", "Paused - You can add more files"))
            self.queue.put(("text", "\nProcessing paused. You can add more files or click 'Resume' to continue.\n"))
        else:
            # Resume - restart timer from where we left off
            if self.pause_start_time:
                # Don't add pause time to elapsed
                self.pause_start_time = None
            self.start_time = time.time()
            # Disable file selection when resuming
            self.select_button.configure(state=tk.DISABLED)
            self.select_folder_button.configure(state=tk.DISABLED)
            self.queue.put(("status", "Resuming..."))
            self.queue.put(("text", "\nResuming processing...\n"))

    def stop_processing(self):
        """Stop processing the queue"""
        self.should_stop = True
        self.is_processing = False
        self.is_paused = False
        self.start_time = None
        self.total_elapsed_seconds = 0
        self.pause_start_time = None
        self.elapsed_time_label["text"] = "Elapsed: 0s"
        
        # Update button states
        self.start_btn.configure(state=tk.NORMAL)
        self.pause_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        self.select_button.configure(state=tk.NORMAL)
        self.select_folder_button.configure(state=tk.NORMAL)
        self.device_combo.configure(state="readonly")
        self.compute_combo.configure(state="readonly")
        self.output_format_combo.configure(state="readonly")
        
        self.queue.put(("status", "Processing stopped"))

    def process_queue(self):
        """Process the file queue"""
        try:
            # Load model once initially; will swap if per-file model differs
            self.queue.put(("text", "Initializing faster-whisper (first time startup, ~10-30 seconds)...\n"))
            self.queue.put(("status", "Loading faster-whisper library..."))
            current_model_name = getattr(self, "worker_initial_model", self.model_var.get())
            model = self.load_model(
                current_model_name,
                device=getattr(self, "worker_device", self.get_selected_device()),
                compute_type=getattr(self, "worker_compute_type", self.get_selected_compute_type())
            )
            self.queue.put(("text", "Model loaded, starting transcription...\n\n"))
            
            pause_notified = False
            while not self.should_stop:
                # Respect pause requests
                while self.is_paused and not self.should_stop:
                    if not pause_notified:
                        self.queue.put(("status", "Paused"))
                        pause_notified = True
                    time.sleep(0.1)
                
                if self.should_stop:
                    break
                
                pause_notified = False
                
                try:
                    task = self.task_queue.get(timeout=0.1)
                except queue.Empty:
                    # Nothing left to do
                    with self.progress_lock:
                        if self.total_tasks == 0 or self.completed_tasks >= self.total_tasks:
                            break
                    continue
                
                item_id = task["item_id"]
                filename = task["filename"]
                include_timestamps = task["include_timestamps"]
                file_path = task["file_path"]
                file_model = task["file_model"]
                overwrite_output = task["overwrite"]
                resume_output = task["resume"]
                output_format = task["output_format"]
                
                # Update file status
                self.queue.put(("file_status", (item_id, "Processing")))
                success = False
                
                # Update status/progress text
                self.queue.put(("status", f"Processing: {filename}"))
                self.queue.put(("text", f"\nStarting transcription of {filename}...\n"))
                
                try:
                    # Verify file still exists and is accessible
                    if not self.is_local_file(file_path):
                        raise FileNotFoundError(f"File is not accessible: {filename}")
                    
                    # Get audio duration using ffprobe
                    try:
                        duration = self.get_audio_duration_seconds(file_path)
                    except ValueError as e:
                        raise ValueError(f"Invalid audio file: {filename}") from e
                        
                    total_minutes = int(duration / 60)
                    self.queue.put(("text", f"Audio length: {total_minutes} minutes\n"))
                    
                    # Show model and processing info
                    self.queue.put(("text", f"Using {file_model} model\n"))
                    self.queue.put(("text", "Transcription in progress...\n"))
                    self.queue.put(("text", "This may take a while. The application will update when complete.\n\n"))

                    # Load the correct model for this file if different from current
                    if file_model != current_model_name:
                        self.queue.put(("text", f"Loading {file_model} model for this file...\n"))
                        model = self.load_model(
                            file_model,
                            device=self.worker_device,
                            compute_type=self.worker_compute_type
                        )
                        current_model_name = file_model

                    # Transcribe file
                    segments, _info = transcribe_segments(model, file_path, task=DEFAULT_TASK_NAME)

                    transcribe_file_include_timestamps = _effective_include_timestamps_for_output(
                        output_format=output_format,
                        include_timestamps=include_timestamps,
                    )
                    transcription = _render_output_text(
                        segments,
                        output_format=output_format,
                        include_timestamps=transcribe_file_include_timestamps,
                    )
                    
                    # Save to file in the same directory as the source file
                    output_file = Path(file_path).parent / f"{Path(file_path).stem}_transcription.{output_format}"

                    metadata_file = resolve_output_metadata_path(output_file)
                    write_metadata_file = build_output_metadata_path(output_file)
                    resume_skip = False
                    if output_file.exists() and resume_output:
                        resume_skip = should_skip_output_due_to_metadata(
                            source_path=file_path,
                            output_path=output_file,
                            metadata_path=metadata_file,
                            model_name=file_model,
                            include_timestamps=transcribe_file_include_timestamps,
                            output_format=output_format,
                            task=DEFAULT_TASK_NAME,
                        )

                    if output_file.exists() and not overwrite_output and resume_skip:
                        self.queue.put(("text", f"\n=== {filename} ===\n"))
                        self.queue.put(("text", f"Resume: skipping completed output file: {output_file}\n\n"))
                        self.queue.put(("status", f"Skipped existing file: {output_file}"))
                        self.queue.put(("file_status", (item_id, "Skipped")))
                        success = True
                        continue

                    if output_file.exists() and not overwrite_output and not resume_output:
                        self.queue.put(("text", f"\n=== {filename} ===\n"))
                        self.queue.put(("text", f"Skipping existing output file: {output_file}\n\n"))
                        self.queue.put(("status", f"Skipped existing file: {output_file}"))
                        self.queue.put(("file_status", (item_id, "Skipped")))
                        success = True
                        continue

                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(transcription)

                    metadata = {
                        "source_path": str(file_path),
                        "output_path": str(output_file),
                        "model": file_model,
                        "include_timestamps": transcribe_file_include_timestamps,
                        "output_format": output_format,
                        "task": DEFAULT_TASK_NAME,
                        "language": None,
                        "overwrite": overwrite_output,
                        "duration_seconds": duration,
                        "created_at": time.time(),
                    }
                    try:
                        with open(write_metadata_file, "w", encoding="utf-8") as f:
                            json.dump(metadata, f, indent=2)
                    except Exception as metadata_error:
                        self.queue.put(("text", f"\nWarning: could not save metadata for {filename}: {metadata_error}\n\n"))
                    
                    # Update text area with completion info
                    self.queue.put(("text", f"\n=== {filename} ===\n"))
                    self.queue.put(("text", "Transcription complete!\n"))
                    self.queue.put(("text", f"Saved to: {output_file}\n\n"))
                    self.queue.put(("text", f"Metadata: {write_metadata_file}\n"))
                    self.queue.put(("status", f"Saved transcription to: {output_file}"))
                    
                    # Update file status
                    self.queue.put(("file_status", (item_id, "Complete")))
                    success = True
                    
                except Exception as e:
                    error_msg = f"Error processing {filename}: {str(e)}"
                    self.queue.put(("text", f"\n=== {filename} ===\n{error_msg}\n"))
                    self.queue.put(("status", error_msg))
                    self.queue.put(("file_status", (item_id, "Error")))
                
                finally:
                    with self.progress_lock:
                        self.completed_tasks += 1
                        if not success:
                            self.failed_tasks += 1
                        self.queue.put((
                            "metrics",
                            {
                                "completed_tasks": self.completed_tasks,
                                "total_tasks": self.total_tasks,
                                "failed_tasks": self.failed_tasks,
                            },
                        ))
                
                # Check for stop or pause after each file
                if self.should_stop:
                    break
            
            if not self.should_stop:
                self.queue.put(("status", "All transcriptions complete!"))
        
        except Exception as e:
            self.queue.put(("status", f"Error: {str(e)}"))
            self.queue.put(("text", f"\nError during processing: {str(e)}\n"))
        
        finally:
            self.is_processing = False
            self.is_paused = False  # Reset pause state
            self.start_time = None
            # Reset button states
            self.queue.put(("button_state", ("start", tk.NORMAL)))
            self.queue.put(("button_state", ("pause", tk.DISABLED)))
            self.queue.put(("button_state", ("stop", tk.DISABLED)))
            self.queue.put(("button_state", ("select", tk.NORMAL)))
            self.queue.put(("button_state", ("select_folder", tk.NORMAL)))
            self.queue.put(("device_state", ("readonly", "readonly", "readonly")))
            self.queue.put(("processing_complete", None))

    def select_files(self):
        """Open file dialog to select audio files."""
        try:
            # Check if we're processing and not paused
            if self.is_processing and not self.is_paused:
                self.queue.put(("text", "\nCannot add files while processing is active.\n"))
                self.queue.put(("text", "Please click 'Pause' first to add more files.\n\n"))
                self.queue.put(("status", "Click 'Pause' to add more files"))
                return

            _ext_glob = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
            filetypes = (
                ("Audio/Video files", _ext_glob),
                ("All files", "*.*")
            )

            try:
                files = filedialog.askopenfilenames(
                    title="Select audio files",
                    filetypes=filetypes
                )
            except Exception as e:
                self.queue.put(("text", f"\nError opening file dialog: {str(e)}\n"))
                self.queue.put(("status", "Error selecting files"))
                return

            if not files:  # User cancelled or no files selected
                return

            self._add_files(sorted(files, key=lambda path: self._file_sort_key(path)))

        except Exception as e:
            self.queue.put(("text", f"\nUnexpected error during file selection: {str(e)}\n"))
            self.queue.put(("status", "Error selecting files"))
            # Reset any state that might have been left in an invalid state
            self.is_processing = False
            self.is_paused = False
            self.start_time = None
            self.start_btn.configure(state=tk.NORMAL)
            self.pause_btn.configure(state=tk.DISABLED)
            self.stop_btn.configure(state=tk.DISABLED)
            self.select_button.configure(state=tk.NORMAL)
            self.select_folder_button.configure(state=tk.NORMAL)

    def select_folder(self):
        """Open folder picker and add all supported media files."""
        try:
            # Check if we're processing and not paused
            if self.is_processing and not self.is_paused:
                self.queue.put(("text", "\nCannot add files while processing is active.\n"))
                self.queue.put(("text", "Please click 'Pause' first to add more files.\n\n"))
                self.queue.put(("status", "Click 'Pause' to add more files"))
                return

            folder = filedialog.askdirectory(title="Select folder containing audio/video files")
            if not folder:
                return

            files = self._collect_supported_files_in_directory(folder)
            if not files:
                self.queue.put(("text", f"\nNo supported files found in: {folder}\n"))
                self.queue.put(("status", "No supported media files found"))
                return

            self._add_files(sorted(files, key=lambda path: self._file_sort_key(path)))

        except Exception as e:
            self.queue.put(("text", f"\nError adding folder: {str(e)}\n"))
            self.queue.put(("status", "Error adding folder"))

    def _collect_supported_files_in_directory(self, folder_path):
        """Return absolute paths for supported files in a folder (recursive)."""
        folder = Path(folder_path)
        if not folder.is_dir():
            return []

        supported_files = []
        for current, _dirs, filenames in os.walk(folder):
            for filename in sorted(filenames):
                candidate = Path(current) / filename
                try:
                    is_file = candidate.is_file()
                except OSError:
                    is_file = False

                if is_file and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    supported_files.append(os.path.abspath(candidate))

        supported_files.sort(key=self._file_sort_key)
        return supported_files

    @staticmethod
    def _file_sort_key(path):
        abs_path = os.path.abspath(path)
        return abs_path.lower(), abs_path

    def _is_already_in_queue(self, file_path):
        normalized = os.path.abspath(file_path)
        for item_id in self.file_list.get_children():
            values = self.file_list.item(item_id)["values"]
            if len(values) >= 5 and os.path.abspath(values[4]) == normalized:
                return item_id
        return None

    def _add_files(self, files):
        """Validate and add file paths to the queue."""
        # Only clear text area if not processing
        if not self.is_processing:
            self.text_area.delete(1.0, tk.END)

        # Add files to list
        for file_path in files:
            try:
                # Convert to absolute path
                file_path = os.path.abspath(file_path)
                filename = os.path.basename(file_path)

                if self._is_already_in_queue(file_path):
                    self.queue.put(("text", f"\nSkipped duplicate file: {filename}\n"))
                    continue

                # Check if file is accessible
                if not self.is_local_file(file_path):
                    self.queue.put(("text", f"\nWarning: Cannot access file: {filename}\n"))
                    if "iCloud Drive" in file_path:
                        self.queue.put(("text", "This file is in iCloud Drive and needs to be downloaded first.\n"))
                        self.queue.put(("text", "Please download it from iCloud Drive before trying again.\n\n"))
                    else:
                        self.queue.put(("text", "Please make sure the file exists and you have permission to access it.\n\n"))

                    # Add file to list with "Not Accessible" status
                    self._insert_file_row(filename, "Not Accessible", file_path)
                    continue

                # Try to get duration to verify file is valid
                try:
                    self.get_audio_duration_seconds(file_path)
                except (subprocess.TimeoutExpired, ValueError):
                    self.queue.put(("text", f"\nWarning: Invalid audio file: {filename}\n"))
                    self.queue.put(("text", "This file appears to be corrupted or is not a valid audio file.\n\n"))

                    # Add file to list with "Invalid" status
                    self._insert_file_row(filename, "Invalid", file_path)
                    continue
                except Exception as e:
                    self.queue.put(("text", f"\nWarning: Could not process {filename}: {str(e)}\n"))
                    self.queue.put(("text", "This file may be corrupted or in an unsupported format.\n\n"))

                    # Add file to list with "Error" status
                    self._insert_file_row(filename, "Error", file_path)
                    continue

                # Add file to list with full path
                item_id = self._insert_file_row(filename, "Pending", file_path)

                # If we're paused mid-run, enqueue the new task so it processes after resume
                if self.is_processing and self.is_paused:
                    self.enqueue_task_from_values(item_id, self.file_list.item(item_id)["values"])

            except Exception as e:
                self.queue.put(("text", f"\nError adding file {file_path}: {str(e)}\n"))
                continue

        # Show model info only if not processing
        if not self.is_processing:
            self.show_model_info()

        # If we're paused, remind user to resume
        if self.is_paused:
            self.queue.put(("text", "\nFiles added successfully. Click 'Resume' to continue processing.\n"))
            self.queue.put(("status", "Files added. Click 'Resume' to continue"))

    def check_queue(self):
        """Check the queue for updates"""
        try:
            while True:
                msg_type, msg_data = self.queue.get_nowait()

                if msg_type == "text":
                    self.text_area.insert(tk.END, msg_data)
                    self.text_area.see(tk.END)
                elif msg_type == "status":
                    self.status_label["text"] = msg_data
                elif msg_type == "file_status":
                    item_id, status = msg_data
                    if not self.file_list.exists(item_id):
                        continue
                    item = item_id
                    values = list(self.file_list.item(item)["values"])
                    values[1] = status
                    self.file_list.item(item, values=values)
                elif msg_type == "button_state":
                    button, state = msg_data
                    if button == "start":
                        self.start_btn.configure(state=state)
                    elif button == "pause":
                        self.pause_btn.configure(state=state)
                    elif button == "stop":
                        self.stop_btn.configure(state=state)
                    elif button == "select":
                        self.select_button.configure(state=state)
                    elif button == "select_folder":
                        self.select_folder_button.configure(state=state)
                elif msg_type == "device_state":
                    device_state, compute_state, output_format_state = msg_data
                    self.device_combo.configure(state=device_state)
                    self.compute_combo.configure(state=compute_state)
                    self.output_format_combo.configure(state=output_format_state)
                elif msg_type == "processing_complete":
                    self.elapsed_time_label["text"] = "Done!"
                elif msg_type == "metrics":
                    completed_tasks = msg_data["completed_tasks"]
                    total_tasks = msg_data["total_tasks"]
                    failed_tasks = msg_data["failed_tasks"]
                    if self.start_time:
                        if self.is_paused and self.pause_start_time:
                            elapsed = self.total_elapsed_seconds
                        else:
                            elapsed = int(time.time() - self.start_time) + self.total_elapsed_seconds
                    else:
                        elapsed = self.total_elapsed_seconds
                    throughput = round(completed_tasks / max(elapsed, 1), 3)
                    self.metrics_label["text"] = (
                        f"Progress: {completed_tasks}/{total_tasks} files, "
                        f"failed: {failed_tasks}, throughput: {throughput} files/sec"
                    )

                self.queue.task_done()
        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.check_queue)

    def on_model_change(self, event=None):
        """Update model info when model selection changes"""
        # Only update the status bar
        model_name = self.model_var.get()
        model_size = MODEL_METADATA[model_name]["size"]
        device_label = self.device_var.get()
        compute_label = self.compute_var.get()
        self.status_label["text"] = (
            f"Selected model: {model_name} ({model_size}), "
            f"{device_label}, {compute_label}"
        )

    def on_device_change(self, event=None):
        """Update compute options when device changes"""
        self.refresh_compute_options()
        self.show_model_info()

    def on_compute_change(self, event=None):
        """Update status when compute type changes"""
        self.show_model_info()

    def refresh_compute_options(self):
        """Update compute choices based on the selected device"""
        device = self.get_selected_device()
        if device == "cuda":
            compute_choices = [
                "Auto (recommended)",
                "Fast (float16)",
                "Balanced (int8_float16)",
                "Memory Saver (int8)",
                "Precise (float32)"
            ]
        else:
            compute_choices = [
                "Auto (recommended)",
                "Memory Saver (int8)",
                "Precise (float32)"
            ]
        current = self.compute_var.get()
        self.compute_combo["values"] = compute_choices
        if current not in compute_choices:
            self.compute_var.set("Auto (recommended)")

    def show_model_info(self):
        """Show information about the selected model"""
        model_name = self.model_var.get()
        model_size = MODEL_METADATA[model_name]["size"]
        model_use_case = MODEL_METADATA[model_name]["use_case"]
        
        # Check which models are downloaded using faster-whisper's cache location
        downloaded_models = []
        for model in SUPPORTED_MODELS:
            model_path = get_model_cache_dir(model)
            if model_path.is_dir():
                downloaded_models.append(model)
        
        # Update status (model info removed per user request)
        if not self.is_processing:
            self.status_label["text"] = "Ready"
        
        # Only show full info in text area if it's empty
        if not self.text_area.get(1.0, tk.END).strip():
            # Build model info text
            info_text = ""
            info_text += f"Size: {model_size}\n"
            info_text += f"Use case: {model_use_case}\n"
            info_text += "The model will be downloaded and run locally with faster-whisper.\n\n"
            
            # Add downloaded models info
            if downloaded_models:
                info_text += "Downloaded models:\n"
                for model in downloaded_models:
                    info_text += f"- {model}: {MODEL_METADATA[model]['size']}\n"
                info_text += "\n"
            else:
                info_text += "No models downloaded yet. The selected model will be downloaded when you start transcription.\n\n"
            
            # Add model selection guidance
            info_text += "Model Selection Guide:\n"
            for model_key in SUPPORTED_MODELS:
                info_text += f"{MODEL_METADATA[model_key]['selection']}\n"
            info_text += "\n"
            
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, info_text)

    def update_remaining_time(self):
        """Update the elapsed time display near control buttons"""
        if self.start_time:
            if self.is_paused and self.pause_start_time:
                # Paused - use accumulated time
                elapsed = self.total_elapsed_seconds
            else:
                # Running - calculate from start
                elapsed = int(time.time() - self.start_time) + self.total_elapsed_seconds
            self.elapsed_time_label["text"] = f"Elapsed: {elapsed}s"
            # Keep updating as long as start_time is set
            self.root.after(1000, self.update_remaining_time)

    def load_model(self, model_name, device=None, compute_type=None):
        """Load the faster-whisper model with download status"""
        try:
            # Get the model path in faster-whisper's cache
            model_path = get_model_cache_dir(model_name)
            is_cached = is_model_cached(model_name)
            model_size = MODEL_METADATA.get(model_name, {}).get("size")
            size_hint = f" ({model_size})" if model_size else ""

            if is_cached:
                self.queue.put(("status", f"Found cached model '{model_name}' at {model_path}{size_hint}."))
                self.queue.put(("text", f"Found cached model '{model_name}' at {model_path}.\n"))
            else:
                self.queue.put(("status", f"Model '{model_name}' not cached yet{size_hint}, downloading now."))
                self.queue.put(
                    ("text", (
                        f"\nDownloading {model_name} model...\n"
                        f"This is a one-time download. The model will be stored locally at:\n{model_path}\n\n"
                    ))
                )

            start = time.perf_counter()

            # Load the model
            model = core_load_model(
                model_name,
                device=device or "auto",
                compute_type=compute_type
            )
            elapsed = time.perf_counter() - start
            
            if is_cached:
                self.queue.put(("status", f"Model '{model_name}' loaded from cache in {elapsed:.2f}s."))
                self.queue.put(("text", f"Model '{model_name}' loaded from cache in {elapsed:.2f}s.\n\n"))
            else:
                self.queue.put(("status", f"Model '{model_name}' download/load finished in {elapsed:.2f}s."))
                self.queue.put(("text", f"Model '{model_name}' download/load finished in {elapsed:.2f}s.\n\n"))

            self.queue.put(("status", f"Model {model_name} loaded successfully"))
            self.queue.put(("text", f"Model {model_name} loaded successfully!\n\n"))
            return model
            
        except Exception as e:
            error_msg = f"Error loading model: {str(e)}"
            self.queue.put(("status", error_msg))
            self.queue.put(("text", f"\nError: {error_msg}\n"))
            raise

    def change_selected_model(self):
        """Change model for selected files"""
        selected = self.file_list.selection()
        if not selected:
            return
        
        # Create a dialog for model selection
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Model")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Add model selection
        ttk.Label(dialog, text="Select new model:").pack(pady=5)
        model_var = tk.StringVar(value=self.model_var.get())
        model_combo = ttk.Combobox(
            dialog,
            textvariable=model_var,
            values=SUPPORTED_MODELS,
            state="readonly",
            width=10
        )
        model_combo.pack(pady=5)
        
        def apply_model_change():
            new_model = model_var.get()
            for item in selected:
                try:
                    values = list(self.file_list.item(item)["values"])
                    if len(values) < 5:  # Ensure we have all required values
                        continue
                        
                    status = values[1]
                    # Only change model for pending files
                    if status == "Pending":
                        values[3] = new_model  # Update model
                        self.file_list.item(item, values=values)
                except Exception as e:
                    print(f"Error processing item: {e}")
                    continue
            
            dialog.destroy()
        
        # Add buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(
            button_frame,
            text="Apply",
            command=apply_model_change
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy
        ).pack(side=tk.LEFT, padx=5)

    def on_drag_start(self, event):
        """Start dragging an item"""
        # Get the item under the cursor
        item = self.file_list.identify_row(event.y)
        if not item:
            return
        
        # Store the item being dragged
        self.drag_item = item
        
        # Get the item's values
        values = self.file_list.item(item)["values"]
        if values[1] != "Pending":  # Only allow dragging pending items
            self.drag_item = None
            return
        
        # Store the initial position
        self.drag_start_index = self.file_list.index(item)
        
        # Change the item's appearance
        self.file_list.tag_configure('dragging', background='#e0e0e0')
        self.file_list.item(item, tags=('dragging',))

    def on_drag_motion(self, event):
        """Handle dragging motion"""
        if not hasattr(self, 'drag_item') or not self.drag_item:
            return
        
        # Get the item under the cursor
        target = self.file_list.identify_row(event.y)
        if not target:
            return
        
        # Get the target's values
        target_values = self.file_list.item(target)["values"]
        if target_values[1] != "Pending":  # Only allow dropping on pending items
            return
        
        # Get the target's position
        target_index = self.file_list.index(target)
        
        # Move the item
        if target_index != self.drag_start_index:
            self.file_list.move(self.drag_item, "", target_index)
            self.drag_start_index = target_index

    def on_drag_release(self, event):
        """Handle end of drag"""
        if hasattr(self, 'drag_item') and self.drag_item:
            # Remove the dragging tag
            self.file_list.item(self.drag_item, tags=())
            self.drag_item = None

    def is_local_file(self, file_path):
        """Check if a file is accessible and readable"""
        try:
            # Try to open the file for reading
            with open(file_path, 'rb') as f:
                # Try to read a small chunk to verify access
                f.read(1024)
            return True
        except (IOError, OSError):
            return False

    def _insert_file_row(self, filename, status, file_path):
        """Insert a file row in the GUI queue and return the item id."""
        return self.file_list.insert(
            "",
            tk.END,
            values=(
                filename,
                status,
                "Yes" if self.timestamps_var.get() else "No",
                self.model_var.get(),
                file_path,
            ),
        )

    def get_audio_duration_seconds(self, file_path):
        """Return audio duration in seconds for a supported file."""
        cmd = [
            'ffprobe',
            '-v',
            'error',
            '-show_entries',
            'format=duration',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            file_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except FileNotFoundError as exc:
            raise ValueError("Missing ffprobe dependency. Install ffmpeg to inspect audio files.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Audio duration probe timed out. Check file accessibility.") from exc

        if result.returncode != 0:
            error = result.stderr.strip() or "ffprobe reported an error"
            raise ValueError(f"Invalid audio file: {error}")

        duration_text = result.stdout.strip()
        if not duration_text:
            raise ValueError("Invalid audio duration: ffprobe output was empty")

        try:
            duration = float(duration_text)
        except ValueError as exc:
            raise ValueError("Invalid audio duration") from exc

        if duration <= 0:
            raise ValueError("Invalid duration")

        return duration

    def get_selected_device(self):
        """Map friendly device label to faster-whisper device string"""
        return self.device_options.get(self.device_var.get(), "auto")

    def get_selected_compute_type(self):
        """Map friendly compute label to faster-whisper compute_type"""
        return self.compute_label_to_type.get(self.compute_var.get())

def main():
    root = tk.Tk()
    _app = TranscriptionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main() 
