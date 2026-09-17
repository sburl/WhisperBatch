import Accelerate
import Foundation

/// Pre-processing that cleans up noisy / staticy recordings before whisper sees
/// them. All functions operate on 16 kHz mono Float32 PCM.
enum AudioEnhancer {
    struct Options: Sendable {
        var bandpass = true
        var denoise = true
        var lowHz: Float = 80
        var highHz: Float = 8000
        var overSubtraction: Float = 1.6
        var spectralFloor: Float = 0.08
    }

    static func enhance(_ samples: [Float], sampleRate: Float = 16000, options: Options = .init()) -> [Float] {
        guard !samples.isEmpty else { return samples }
        var s = samples
        if options.bandpass {
            s = biquad(s, coeffs: highpassCoeffs(cutoff: options.lowHz, sampleRate: sampleRate))
            s = biquad(s, coeffs: lowpassCoeffs(cutoff: min(options.highHz, sampleRate / 2 - 100), sampleRate: sampleRate))
        }
        if options.denoise {
            s = spectralSubtract(s, overSubtraction: options.overSubtraction, floor: options.spectralFloor)
        }
        return s
    }

    struct BiquadCoeffs { var b0, b1, b2, a1, a2: Float }

    static func highpassCoeffs(cutoff: Float, sampleRate: Float, q: Float = 0.707) -> BiquadCoeffs {
        let w0 = 2 * Float.pi * cutoff / sampleRate
        let cosw = cos(w0), sinw = sin(w0)
        let alpha = sinw / (2 * q)
        let a0 = 1 + alpha
        return BiquadCoeffs(
            b0: ((1 + cosw) / 2) / a0,
            b1: (-(1 + cosw)) / a0,
            b2: ((1 + cosw) / 2) / a0,
            a1: (-2 * cosw) / a0,
            a2: (1 - alpha) / a0
        )
    }

    static func lowpassCoeffs(cutoff: Float, sampleRate: Float, q: Float = 0.707) -> BiquadCoeffs {
        let w0 = 2 * Float.pi * cutoff / sampleRate
        let cosw = cos(w0), sinw = sin(w0)
        let alpha = sinw / (2 * q)
        let a0 = 1 + alpha
        return BiquadCoeffs(
            b0: ((1 - cosw) / 2) / a0,
            b1: (1 - cosw) / a0,
            b2: ((1 - cosw) / 2) / a0,
            a1: (-2 * cosw) / a0,
            a2: (1 - alpha) / a0
        )
    }

    static func biquad(_ x: [Float], coeffs c: BiquadCoeffs) -> [Float] {
        var y = [Float](repeating: 0, count: x.count)
        var x1: Float = 0, x2: Float = 0, y1: Float = 0, y2: Float = 0
        for n in 0..<x.count {
            let xn = x[n]
            let yn = c.b0 * xn + c.b1 * x1 + c.b2 * x2 - c.a1 * y1 - c.a2 * y2
            y[n] = yn
            x2 = x1; x1 = xn
            y2 = y1; y1 = yn
        }
        return y
    }

    static func spectralSubtract(_ samples: [Float], frameSize: Int = 512, overSubtraction: Float = 1.6, floor: Float = 0.08) -> [Float] {
        let n = samples.count
        guard n >= frameSize else { return samples }
        let hop = frameSize / 2
        let half = frameSize / 2
        let log2n = vDSP_Length(log2(Float(frameSize)))
        guard let setup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else { return samples }
        defer { vDSP_destroy_fftsetup(setup) }

        var window = [Float](repeating: 0, count: frameSize)
        vDSP_hann_window(&window, vDSP_Length(frameSize), Int32(vDSP_HANN_NORM))

        var output = [Float](repeating: 0, count: n)
        var windowSum = [Float](repeating: 0, count: n)

        var realp = [Float](repeating: 0, count: half)
        var imagp = [Float](repeating: 0, count: half)
        var noiseMag = [Float](repeating: 0, count: half)
        var noiseInitialized = false
        let scale: Float = 1.0 / Float(2 * frameSize)

        var frame = [Float](repeating: 0, count: frameSize)
        var start = 0
        while start + frameSize <= n {
            for i in 0..<frameSize { frame[i] = samples[start + i] * window[i] }

            realp.withUnsafeMutableBufferPointer { rp in
                imagp.withUnsafeMutableBufferPointer { ip in
                    var split = DSPSplitComplex(realp: rp.baseAddress!, imagp: ip.baseAddress!)
                    frame.withUnsafeBufferPointer { fp in
                        fp.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: half) { cp in
                            vDSP_ctoz(cp, 2, &split, 1, vDSP_Length(half))
                        }
                    }
                    vDSP_fft_zrip(setup, &split, 1, log2n, FFTDirection(FFT_FORWARD))

                    var mag = [Float](repeating: 0, count: half)
                    mag[0] = abs(rp[0])
                    for k in 1..<half { mag[k] = sqrt(rp[k] * rp[k] + ip[k] * ip[k]) }
                    let nyquistMag = abs(ip[0])

                    let frameEnergy = mag.reduce(0) { $0 + $1 * $1 }
                    if !noiseInitialized {
                        noiseMag = mag
                        noiseInitialized = true
                    } else {
                        let noiseEnergy = noiseMag.reduce(0) { $0 + $1 * $1 }
                        if frameEnergy < 2.0 * noiseEnergy {
                            for k in 0..<half { noiseMag[k] = 0.9 * noiseMag[k] + 0.1 * mag[k] }
                        }
                    }

                    func gain(_ m: Float, _ nz: Float) -> Float {
                        guard m > 1e-9 else { return floor }
                        return Swift.max(floor, (m - overSubtraction * nz) / m)
                    }
                    rp[0] *= gain(mag[0], noiseMag[0])
                    ip[0] *= gain(nyquistMag, noiseMag[0])
                    for k in 1..<half {
                        let g = gain(mag[k], noiseMag[k])
                        rp[k] *= g
                        ip[k] *= g
                    }

                    vDSP_fft_zrip(setup, &split, 1, log2n, FFTDirection(FFT_INVERSE))
                    var recon = [Float](repeating: 0, count: frameSize)
                    recon.withUnsafeMutableBufferPointer { rb in
                        rb.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: half) { cp in
                            vDSP_ztoc(&split, 1, cp, 2, vDSP_Length(half))
                        }
                    }
                    var sc = scale
                    vDSP_vsmul(recon, 1, &sc, &recon, 1, vDSP_Length(frameSize))

                    for i in 0..<frameSize {
                        output[start + i] += recon[i] * window[i]
                        windowSum[start + i] += window[i] * window[i]
                    }
                }
            }
            start += hop
        }

        for i in 0..<n where windowSum[i] > 1e-6 { output[i] /= windowSum[i] }
        if start < n {
            for i in start..<n where windowSum[i] <= 1e-6 { output[i] = samples[i] }
        }
        return output
    }
}
