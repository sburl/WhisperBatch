import XCTest
@testable import WhisperBatchCore

final class AudioEnhancerTests: XCTestCase {
    private let fs: Float = 16000

    private func tone(_ hz: Float, seconds: Float = 1, amplitude: Float = 0.5) -> [Float] {
        let count = Int(fs * seconds)
        return (0..<count).map { amplitude * sin(2 * .pi * hz * Float($0) / fs) }
    }

    private func rms(_ x: [Float]) -> Float {
        guard !x.isEmpty else { return 0 }
        return sqrt(x.reduce(0) { $0 + $1 * $1 } / Float(x.count))
    }

    private func core(_ x: [Float]) -> [Float] {
        let pad = min(2000, x.count / 4)
        return Array(x[pad..<(x.count - pad)])
    }

    func testHighpassAttenuatesSubBass() {
        let input = tone(50)
        let out = AudioEnhancer.biquad(input, coeffs: AudioEnhancer.highpassCoeffs(cutoff: 80, sampleRate: fs))
        XCTAssertLessThan(rms(core(out)), 0.5 * rms(core(input)), "50 Hz should be cut by an 80 Hz high-pass")
    }

    func testHighpassPassesSpeechBand() {
        let input = tone(1000)
        let out = AudioEnhancer.biquad(input, coeffs: AudioEnhancer.highpassCoeffs(cutoff: 80, sampleRate: fs))
        XCTAssertGreaterThan(rms(core(out)), 0.8 * rms(core(input)), "1 kHz should pass an 80 Hz high-pass")
    }

    func testLowpassAttenuatesHiss() {
        let input = tone(6000)
        let out = AudioEnhancer.biquad(input, coeffs: AudioEnhancer.lowpassCoeffs(cutoff: 2000, sampleRate: fs))
        XCTAssertLessThan(rms(core(out)), 0.5 * rms(core(input)), "6 kHz should be cut by a 2 kHz low-pass")
    }

    func testLowpassPassesSpeechBand() {
        let input = tone(1000)
        let out = AudioEnhancer.biquad(input, coeffs: AudioEnhancer.lowpassCoeffs(cutoff: 7000, sampleRate: fs))
        XCTAssertGreaterThan(rms(core(out)), 0.8 * rms(core(input)), "1 kHz should pass a 7 kHz low-pass")
    }

    func testDenoiseReducesStationaryNoise() {
        var seed: UInt64 = 0x9E3779B97F4A7C15
        func next() -> Float {
            seed = seed &* 6364136223846793005 &+ 1442695040888963407
            return Float(Int32(truncatingIfNeeded: seed >> 33)) / Float(Int32.max)
        }
        let noise = (0..<16000).map { _ in 0.3 * next() }
        let out = AudioEnhancer.spectralSubtract(noise)
        XCTAssertEqual(out.count, noise.count)
        XCTAssertLessThan(rms(out), 0.8 * rms(noise), "stationary noise floor should drop")
        XCTAssertFalse(out.contains { $0.isNaN || $0.isInfinite }, "no NaN/Inf in output")
    }

    func testEnhanceShortInputIsSafe() {
        XCTAssertEqual(AudioEnhancer.enhance([]).count, 0)
        let tiny: [Float] = [0.1, -0.2, 0.3]
        XCTAssertEqual(AudioEnhancer.enhance(tiny).count, tiny.count)
    }

    func testEnhancePreservesLength() {
        let input = tone(440, seconds: 2)
        XCTAssertEqual(AudioEnhancer.enhance(input).count, input.count)
    }
}
