import XCTest
@testable import WhisperBatchCore

final class TimeFormatterTests: XCTestCase {

    func testSecondsOnly() {
        XCTAssertEqual(TimeFormatter.formatDuration(45), "45s")
    }

    func testMinutesAndSeconds() {
        XCTAssertEqual(TimeFormatter.formatDuration(125), "2m 5s")
    }

    func testHoursMinutesSeconds() {
        XCTAssertEqual(TimeFormatter.formatDuration(3661), "1h 1m 1s")
    }

    func testZero() {
        XCTAssertEqual(TimeFormatter.formatDuration(0), "0s")
    }

    func testNegative() {
        XCTAssertEqual(TimeFormatter.formatDuration(-5), "0s")
    }

    func testCompactSeconds() {
        XCTAssertEqual(TimeFormatter.formatDurationCompact(45), "0:45")
    }

    func testCompactMinutes() {
        XCTAssertEqual(TimeFormatter.formatDurationCompact(125), "2:05")
    }

    func testCompactHours() {
        XCTAssertEqual(TimeFormatter.formatDurationCompact(3661), "1:01:01")
    }
}
