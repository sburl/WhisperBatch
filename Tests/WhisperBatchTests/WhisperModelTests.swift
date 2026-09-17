import XCTest
@testable import WhisperBatchCore

final class WhisperModelTests: XCTestCase {
    func testLargeV3TurboCatalogMetadata() {
        let model = WhisperModelType.largeV3Turbo

        XCTAssertEqual(model.rawValue, "large-v3-turbo")
        XCTAssertEqual(model.ggmlFilename, "ggml-large-v3-turbo-q5_0.bin")
        XCTAssertEqual(
            model.downloadURL.absoluteString,
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin"
        )
        XCTAssertFalse(model.requiresMLX)
        XCTAssertTrue(WhisperModelType.ggmlDownloadable.contains(model))
        XCTAssertEqual(
            model.expectedSHA256,
            "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"
        )
    }
}
