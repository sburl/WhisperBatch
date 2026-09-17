import AppKit

#if !APP_STORE
import Sparkle
#endif

final class AppDelegate: NSObject, NSApplicationDelegate {
    #if !APP_STORE
    private var updaterController: SPUStandardUpdaterController?
    #endif

    func applicationDidFinishLaunching(_ notification: Notification) {
        #if !APP_STORE
        updaterController = SPUStandardUpdaterController(
            startingUpdater: true,
            updaterDelegate: nil,
            userDriverDelegate: nil
        )
        #endif
    }

    #if !APP_STORE
    @MainActor @objc func checkForUpdates(_ sender: Any?) {
        updaterController?.checkForUpdates(sender)
    }
    #endif
}
