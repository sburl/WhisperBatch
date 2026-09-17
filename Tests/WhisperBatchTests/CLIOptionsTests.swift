import XCTest
@testable import WhisperBatchCLI
import WhisperBatchCore

final class CLIOptionsTests: XCTestCase {
    func testDefaults() throws {
        let options = try CLIOptions.parse(["sample.mp4"])

        XCTAssertEqual(options.inputs, ["sample.mp4"])
        XCTAssertEqual(options.model, .largeV3Turbo)
        XCTAssertEqual(options.format, .single(.txt))
        XCTAssertNil(options.output)
        XCTAssertNil(options.language)
        XCTAssertFalse(options.skipSilence)
    }

    func testParsesFlagsAndMultipleInputs() throws {
        let options = try CLIOptions.parse([
            "a.mp3",
            "b.mov",
            "--model", "small",
            "--format", "srt",
            "--output", "/tmp/out",
            "--language", "en",
            "--skip-silence",
        ])

        XCTAssertEqual(options.inputs, ["a.mp3", "b.mov"])
        XCTAssertEqual(options.model, .small)
        XCTAssertEqual(options.format, .single(.srt))
        XCTAssertEqual(options.output, "/tmp/out")
        XCTAssertEqual(options.language, "en")
        XCTAssertTrue(options.skipSilence)
    }

    func testRejectsInvalidFormat() {
        XCTAssertThrowsError(try CLIOptions.parse(["sample.mp4", "--format", "xml"])) { error in
            XCTAssertEqual(error as? CLIParseError, .invalidFormat("xml"))
        }
    }

    func testRejectsMissingInput() {
        XCTAssertThrowsError(try CLIOptions.parse(["--format", "json"])) { error in
            XCTAssertEqual(error as? CLIParseError, .missingInput)
        }
    }
}
