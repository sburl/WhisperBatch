import Foundation

public enum WhisperModelType: String, CaseIterable, Identifiable, Codable, Sendable {
    case tiny
    case small
    case largeV3Turbo = "large-v3-turbo"
    case largeV3 = "large-v3"
    case turbo          // mlx-whisper distil-large-v3 — Metal only (dev build)

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .tiny:         "Tiny · Fastest"
        case .small:        "Small · Balanced"
        case .largeV3Turbo: "Large Turbo · Recommended"
        case .largeV3:      "Large · Best Quality"
        case .turbo:        "Turbo (Metal, dev only)"
        }
    }

    public var sizeDescription: String {
        switch self {
        case .tiny:         "~75 MB"
        case .small:        "~190 MB"
        case .largeV3Turbo: "~574 MB"
        case .largeV3:      "~1.1 GB"
        case .turbo:        "~1.5 GB (distil-large-v3)"
        }
    }

    public var useCase: String {
        switch self {
        case .tiny:         "Quick drafts and clear speech"
        case .small:        "Light and fast · a third the size of Large Turbo"
        case .largeV3Turbo: "Near-Large accuracy, much faster · best all-round"
        case .largeV3:      "Maximum accuracy, slowest"
        case .turbo:        "Metal-accelerated, large-v3 accuracy at ~8× real-time"
        }
    }

    /// Friendly relative-speed label derived from `estimatedSpeed` — sets the
    /// user's expectation. "~6× real-time" means ~10 min of audio in ~1.7 min.
    public var speedDescription: String {
        "~\(Int(estimatedSpeed))× real-time"
    }

    /// Whether this model is only available via the mlx-whisper backend (dev build).
    public var requiresMLX: Bool { self == .turbo }

    /// Models that can be downloaded as GGML (whisper.cpp) binaries.
    public static var ggmlDownloadable: [WhisperModelType] {
        allCases.filter { !$0.requiresMLX }
    }

    /// Filename of the GGML model binary (whisper.cpp backend only).
    ///
    /// Tiny ships bundled as full-precision f16 for instant offline first-launch.
    /// Every downloadable model uses a quantized (q5) build instead of f16: the
    /// same model weights, ~3× smaller download, lower RAM, faster CPU inference,
    /// with negligible accuracy loss (q5 is the community-standard sweet spot).
    public var ggmlFilename: String {
        switch self {
        case .tiny:         "ggml-tiny.bin"
        case .small:        "ggml-small-q5_1.bin"
        case .largeV3Turbo: "ggml-large-v3-turbo-q5_0.bin"
        case .largeV3:      "ggml-large-v3-q5_0.bin"
        // MLX-only; excluded from ggmlDownloadable, so this is never fetched.
        case .turbo:        "ggml-turbo.bin"
        }
    }

    /// HuggingFace download URL for the GGML model.
    public var downloadURL: URL {
        URL(string: "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/\(ggmlFilename)")!
    }

    /// Published SHA-256 for the GGML blob in ggerganov/whisper.cpp
    /// (the Hugging Face LFS object IDs for the downloadable binaries).
    public var expectedSHA256: String? {
        switch self {
        case .tiny:
            "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21"
        case .small:
            "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb"
        case .largeV3Turbo:
            "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"
        case .largeV3:
            "d75795ecff3f83b5faa89d1900604ad8c780abd5739fae406de19f23ecd98ad1"
        case .turbo:
            nil
        }
    }

    /// HuggingFace repo ID used by mlx-whisper (dev build; ignored for GGML).
    public var mlxRepoID: String {
        switch self {
        case .tiny:         "mlx-community/whisper-tiny-mlx"
        case .small:        "mlx-community/whisper-small-mlx"
        case .largeV3Turbo: "mlx-community/whisper-large-v3-turbo"
        case .largeV3:      "mlx-community/whisper-large-v3-mlx"
        case .turbo:        "mlx-community/distil-whisper-large-v3"
        }
    }

    /// WhisperKit CoreML model variant (from the argmaxinc/whisperkit-coreml repo).
    /// large-v3-v20240930 IS OpenAI's large-v3-turbo; the 626MB build is the
    /// M-series-recommended turbo variant. Large maps to full large-v3.
    public var whisperKitModelName: String {
        switch self {
        case .tiny:         "openai_whisper-tiny"
        case .small:        "openai_whisper-small"
        case .largeV3Turbo: "openai_whisper-large-v3-v20240930_626MB"
        case .largeV3:      "openai_whisper-large-v3"
        case .turbo:        "openai_whisper-large-v3-v20240930_turbo_632MB"
        }
    }

    /// Estimated transcription speed relative to real-time on Apple Silicon.
    /// Rough expectation-setting values for the quantized q5 models on the CPU
    /// engine; the turbo/MLX figure is a literature estimate, not a device run.
    public var estimatedSpeed: Double {
        switch self {
        case .tiny:          15.0
        case .small:          8.0
        case .largeV3Turbo:   6.0
        case .largeV3:        2.0
        case .turbo:          8.0
        }
    }
}
