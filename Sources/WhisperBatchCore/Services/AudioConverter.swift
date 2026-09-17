import AVFoundation
import CoreMedia
import Foundation

public enum AudioConversionError: LocalizedError {
    case cannotCreateReader
    case cannotCreateOutput
    case conversionFailed(String)
    case noAudioTrack

    public var errorDescription: String? {
        switch self {
        case .cannotCreateReader:
            return "Cannot create audio reader."
        case .cannotCreateOutput:
            return "Cannot create audio output."
        case .conversionFailed(let message):
            return "Audio conversion failed: \(message)"
        case .noAudioTrack:
            return "File contains no audio tracks."
        }
    }
}

public struct AudioConverter {
    public static let sampleRate = 16000
    public static let defaultChunkDuration: TimeInterval = 30 * 60
    public static let defaultChunkSampleCount = sampleRate * Int(defaultChunkDuration)

    /// Convert audio/video file to 16kHz mono Float32 PCM samples.
    /// This is what SwiftWhisper expects as input.
    public static func convertToFloat32PCM(
        url: URL,
        timeRange: CMTimeRange? = nil,
        enhanceAudio: Bool = false
    ) async throws -> [Float] {
        var samples: [Float] = []
        try await convertToFloat32PCMChunks(url: url, timeRange: timeRange, enhanceAudio: enhanceAudio) { chunk, _ in
            samples.append(contentsOf: chunk)
        }
        return samples
    }

    /// Decode audio/video file to 16kHz mono Float32 PCM and deliver bounded chunks.
    public static func convertToFloat32PCMChunks(
        url: URL,
        timeRange: CMTimeRange? = nil,
        chunkSampleCount: Int = defaultChunkSampleCount,
        enhanceAudio: Bool = false,
        cancellationToken: CancellationToken? = nil,
        onChunk: (_ samples: [Float], _ startTime: TimeInterval) async throws -> Void
    ) async throws {
        precondition(chunkSampleCount > 0)
        let asset = AVAsset(url: url)

        let tracks: [AVAssetTrack]
        do {
            tracks = try await asset.loadTracks(withMediaType: .audio)
        } catch {
            throw AudioConversionError.conversionFailed(error.localizedDescription)
        }

        guard !tracks.isEmpty else {
            throw AudioConversionError.noAudioTrack
        }

        let outputSettings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 32,
            AVLinearPCMIsFloatKey: true,
            AVLinearPCMIsBigEndianKey: false,
            AVLinearPCMIsNonInterleaved: false,
        ]

        let reader: AVAssetReader
        do {
            reader = try AVAssetReader(asset: asset)
        } catch {
            throw AudioConversionError.cannotCreateReader
        }
        if let timeRange {
            reader.timeRange = timeRange
        }

        let output = AVAssetReaderAudioMixOutput(audioTracks: tracks, audioSettings: outputSettings)
        guard reader.canAdd(output) else {
            throw AudioConversionError.cannotCreateOutput
        }
        reader.add(output)

        guard reader.startReading() else {
            let message = reader.error?.localizedDescription ?? "Unknown error"
            throw AudioConversionError.conversionFailed(message)
        }

        var chunk: [Float] = []
        chunk.reserveCapacity(min(chunkSampleCount, sampleRate * 60))
        var emittedSamples = 0

        while let sampleBuffer = output.copyNextSampleBuffer() {
            if cancellationToken?.isCancelled == true {
                reader.cancelReading()
                throw TranscriptionError.cancelled
            }

            guard let blockBuffer = CMSampleBufferGetDataBuffer(sampleBuffer) else {
                continue
            }

            let length = CMBlockBufferGetDataLength(blockBuffer)
            var data = Data(count: length)
            data.withUnsafeMutableBytes { rawBuffer in
                guard let baseAddress = rawBuffer.baseAddress else { return }
                CMBlockBufferCopyDataBytes(blockBuffer, atOffset: 0, dataLength: length, destination: baseAddress)
            }

            let floatCount = length / MemoryLayout<Float>.size
            let floatArray = data.withUnsafeBytes { rawBuffer in
                Array(UnsafeBufferPointer(
                    start: rawBuffer.baseAddress!.assumingMemoryBound(to: Float.self),
                    count: floatCount
                ))
            }

            var offset = 0
            while offset < floatArray.count {
                let capacity = chunkSampleCount - chunk.count
                let count = min(capacity, floatArray.count - offset)
                chunk.append(contentsOf: floatArray[offset..<(offset + count)])
                offset += count

                if chunk.count == chunkSampleCount {
                    let startTime = cropStartOffset(timeRange) + Double(emittedSamples) / Double(sampleRate)
                    try await onChunk(enhanceAudio ? AudioEnhancer.enhance(chunk) : chunk, startTime)
                    emittedSamples += chunk.count
                    chunk.removeAll(keepingCapacity: true)
                }
            }
        }

        if reader.status == .failed {
            let message = reader.error?.localizedDescription ?? "Unknown error"
            throw AudioConversionError.conversionFailed(message)
        }

        if !chunk.isEmpty {
            let startTime = cropStartOffset(timeRange) + Double(emittedSamples) / Double(sampleRate)
            try await onChunk(enhanceAudio ? AudioEnhancer.enhance(chunk) : chunk, startTime)
        }
    }

    public static func duration(url: URL) async throws -> TimeInterval {
        let asset = AVAsset(url: url)
        do {
            let duration = try await asset.load(.duration)
            return CMTimeGetSeconds(duration)
        } catch {
            throw AudioConversionError.conversionFailed(error.localizedDescription)
        }
    }

    private static func cropStartOffset(_ timeRange: CMTimeRange?) -> TimeInterval {
        guard let timeRange else { return 0 }
        let seconds = CMTimeGetSeconds(timeRange.start)
        return seconds.isFinite ? seconds : 0
    }
}
