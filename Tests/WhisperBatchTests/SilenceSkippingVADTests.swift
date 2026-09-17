import XCTest
@testable import WhisperBatchCore

final class SilenceSkippingVADTests: XCTestCase {
    func testSilenceProducesNoSpeechRegions() {
        let vad = SilenceSkippingVAD()
        let samples = Array(repeating: Float(0), count: AudioConverter.sampleRate * 2)

        XCTAssertEqual(vad.speechRegions(in: samples), [])
    }

    func testToneProducesSpeechRegion() throws {
        let vad = SilenceSkippingVAD()
        var samples = Array(repeating: Float(0), count: AudioConverter.sampleRate)
        samples.append(contentsOf: tone(duration: 1.0, frequency: 440, amplitude: 0.2))
        samples.append(contentsOf: Array(repeating: Float(0), count: AudioConverter.sampleRate))

        let regions = vad.speechRegions(in: samples)

        XCTAssertEqual(regions.count, 1)
        let region = try XCTUnwrap(regions.first)
        XCTAssertLessThanOrEqual(region.startSample, AudioConverter.sampleRate)
        XCTAssertGreaterThanOrEqual(region.endSample, AudioConverter.sampleRate * 2)
    }

    func testQuietToneBelowThresholdIsSkipped() {
        let vad = SilenceSkippingVAD(energyThreshold: 0.01)
        let samples = tone(duration: 1.0, frequency: 440, amplitude: 0.001)

        XCTAssertEqual(vad.speechRegions(in: samples), [])
    }

    private func tone(duration: TimeInterval, frequency: Double, amplitude: Float) -> [Float] {
        let count = Int(duration * Double(AudioConverter.sampleRate))
        return (0..<count).map { index in
            let phase = 2.0 * Double.pi * frequency * Double(index) / Double(AudioConverter.sampleRate)
            return Float(sin(phase)) * amplitude
        }
    }
}
