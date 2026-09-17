import AVFoundation
import Foundation

public enum WaveformError: LocalizedError {
    case noAudioTrack
    case readFailed(String)

    public var errorDescription: String? {
        switch self {
        case .noAudioTrack: "File contains no audio tracks."
        case .readFailed(let message): "Could not read audio for waveform: \(message)"
        }
    }
}

public enum WaveformGenerator {
    public static func generate(url: URL, buckets: Int = 1600, sampleRate: Double = 16000) async throws -> [Float] {
        let asset = AVAsset(url: url)
        let tracks = try await asset.loadTracks(withMediaType: .audio)
        guard !tracks.isEmpty else { throw WaveformError.noAudioTrack }
        let duration = try await asset.load(.duration)
        let totalFrames = max(1, Int(duration.seconds * sampleRate))
        let framesPerBucket = max(1, totalFrames / max(1, buckets))

        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: sampleRate,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 32,
            AVLinearPCMIsFloatKey: true,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsNonInterleaved: false,
        ]

        guard let reader = try? AVAssetReader(asset: asset) else {
            throw WaveformError.readFailed("reader")
        }
        let output = AVAssetReaderAudioMixOutput(audioTracks: tracks, audioSettings: settings)
        guard reader.canAdd(output) else { throw WaveformError.readFailed("output") }
        reader.add(output)
        guard reader.startReading() else {
            throw WaveformError.readFailed(reader.error?.localizedDescription ?? "start")
        }

        var peaks: [Float] = []
        peaks.reserveCapacity(buckets)
        var current: Float = 0
        var countInBucket = 0

        while let sampleBuffer = output.copyNextSampleBuffer() {
            guard let block = CMSampleBufferGetDataBuffer(sampleBuffer) else { continue }
            let length = CMBlockBufferGetDataLength(block)
            var data = Data(count: length)
            data.withUnsafeMutableBytes { raw in
                guard let base = raw.baseAddress else { return }
                CMBlockBufferCopyDataBytes(block, atOffset: 0, dataLength: length, destination: base)
            }
            let floatCount = length / MemoryLayout<Float>.size
            data.withUnsafeBytes { raw in
                let ptr = raw.baseAddress!.assumingMemoryBound(to: Float.self)
                for i in 0..<floatCount {
                    let v = abs(ptr[i])
                    if v > current { current = v }
                    countInBucket += 1
                    if countInBucket >= framesPerBucket {
                        peaks.append(current)
                        current = 0
                        countInBucket = 0
                    }
                }
            }
        }
        if countInBucket > 0 { peaks.append(current) }

        if reader.status == .failed {
            throw WaveformError.readFailed(reader.error?.localizedDescription ?? "read")
        }
        return normalize(peaks)
    }

    public static func normalize(_ peaks: [Float]) -> [Float] {
        guard let maxPeak = peaks.max(), maxPeak > 0 else { return peaks }
        return peaks.map { $0 / maxPeak }
    }

    public static func bucketPeaks(from samples: [Float], buckets: Int) -> [Float] {
        guard buckets > 0, !samples.isEmpty else { return [] }
        let framesPerBucket = max(1, samples.count / buckets)
        var peaks: [Float] = []
        var current: Float = 0
        var countInBucket = 0
        for v in samples {
            let a = abs(v)
            if a > current { current = a }
            countInBucket += 1
            if countInBucket >= framesPerBucket {
                peaks.append(current)
                current = 0
                countInBucket = 0
            }
        }
        if countInBucket > 0 { peaks.append(current) }
        return peaks
    }
}
