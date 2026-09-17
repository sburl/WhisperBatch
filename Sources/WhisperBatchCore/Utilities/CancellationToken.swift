import Foundation

public final class CancellationToken: @unchecked Sendable {
    private let lock = NSLock()
    private var _isCancelled = false

    public init() {}

    public var isCancelled: Bool {
        lock.withLock { _isCancelled }
    }

    public func cancel() {
        lock.withLock {
            _isCancelled = true
        }
    }
}
