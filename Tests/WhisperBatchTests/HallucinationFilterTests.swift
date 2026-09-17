import XCTest
@testable import WhisperBatchCore

final class HallucinationFilterTests: XCTestCase {
    private func seg(_ start: Double, _ end: Double, _ text: String) -> TranscriptionSegment {
        TranscriptionSegment(start: start, end: end, text: text)
    }

    func testCollapsesLongRepeatRun() {
        let input = (0..<5).map { seg(Double($0), Double($0) + 1, "Claude & Claude") }
        let out = HallucinationFilter.clean(input)
        XCTAssertEqual(out.count, 1)
        XCTAssertEqual(out.first?.start, 0)
        XCTAssertEqual(out.first?.end, 5)
        XCTAssertEqual(out.first?.text, "Claude & Claude")
    }

    func testKeepsShortNaturalRepeats() {
        let input = [seg(0, 1, "yeah"), seg(1, 2, "yeah"), seg(2, 3, "okay")]
        let out = HallucinationFilter.clean(input)
        XCTAssertEqual(out.count, 3)
    }

    func testDropsNonSpeechTokens() {
        let input = [
            seg(0, 1, "[SOLAR NOISE, NENDA]"),
            seg(1, 2, "(static)"),
            seg(2, 3, "*Jingle Bells*"),
            seg(3, 4, "♪♪♪"),
            seg(4, 5, "Hello there"),
        ]
        let out = HallucinationFilter.clean(input)
        XCTAssertEqual(out.map(\.text), ["Hello there"])
    }

    func testDropsEmptyAndWhitespace() {
        let input = [seg(0, 1, "   "), seg(1, 2, "\n"), seg(2, 3, "real text")]
        let out = HallucinationFilter.clean(input)
        XCTAssertEqual(out.map(\.text), ["real text"])
    }

    func testTrimsWhitespace() {
        let out = HallucinationFilter.clean([seg(0, 1, "  hi there  ")])
        XCTAssertEqual(out.first?.text, "hi there")
    }

    func testNormalizedRepeatIsCaseInsensitive() {
        let input = [seg(0, 1, "Claude"), seg(1, 2, "claude"), seg(2, 3, "CLAUDE")]
        let out = HallucinationFilter.clean(input)
        XCTAssertEqual(out.count, 1)
    }

    func testRealSpeechPassesThrough() {
        let input = [
            seg(0, 2, "I found a few boxes to put stuff in"),
            seg(2, 4, "what kind of stuff are you doing?"),
            seg(4, 6, "I have these credit cards"),
        ]
        let out = HallucinationFilter.clean(input)
        XCTAssertEqual(out.count, 3)
    }

    func testEmptyInput() {
        XCTAssertEqual(HallucinationFilter.clean([]).count, 0)
    }
}
