import SwiftUI
import WhisperBatchCore

@main
struct WhisperBatchApp: App {
    #if !APP_STORE
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    #endif

    @State private var fileQueueVM = FileQueueViewModel()
    @State private var transcriptionVM = TranscriptionViewModel()
    @State private var modelManagerVM = ModelManagerViewModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(fileQueueVM)
                .environment(transcriptionVM)
                .environment(modelManagerVM)
        }
        .defaultSize(width: 600, height: 350)
        .commands {
            CommandGroup(after: .newItem) {
                Button("Add Files...") {
                    fileQueueVM.showFilePicker = true
                }
                .keyboardShortcut("o", modifiers: .command)
            }
        }

        Settings {
            SettingsView()
                .environment(modelManagerVM)
        }
    }
}
