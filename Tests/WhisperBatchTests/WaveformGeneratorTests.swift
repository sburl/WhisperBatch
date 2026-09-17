import XCTest
@testable import WhisperBatchCore

final class WaveformGeneratorTests: XCTestCase {
    func testBucketPeaksReturnsRequestedResolution() {
        let samples = (0..<1000).map { _ in Float.random(in: -1...1) }
        let peaks = WaveformGenerator.bucketPeaks(from: samples, buckets: 100)
        XCTAssertEqual(peaks.count, 100)
    }

    func testBucketPeaksTakesMaxAbsPerBucket() {
        let samples: [Float] = [0.1, -0.9, 0.2, 0.3, 0.4, 0.1]
        let peaks = WaveformGenerator.bucketPeaks(from: samples, buckets: 2)
        XCTAssertEqual(peaks.count, 2)
        XCTAssertEqual(peaks[0], 0.9, accuracy: 0.0001)
        XCTAssertEqual(peaks[1], 0.4, accuracy: 0.0001)
    }

    func testBucketPeaksEmpty() {
        XCTAssertEqual(WaveformGenerator.bucketPeaks(from: [], buckets: 10).count, 0)
        XCTAssertEqual(WaveformGenerator.bucketPeaks(from: [0.5], buckets: 0).count, 0)
    }

    func testNormalizeScalesLoudestToOne() {
        let out = WaveformGenerator.normalize([0.1, 0.25, 0.5])
        XCTAssertEqual(out.max() ?? 0, 1.0, accuracy: 0.0001)
        XCTAssertEqual(out[0], 0.2, accuracy: 0.0001)
    }

    func testNormalizeAllZeroIsSafe() {
        XCTAssertEqual(WaveformGenerator.normalize([0, 0, 0]), [0, 0, 0])
    }
}
