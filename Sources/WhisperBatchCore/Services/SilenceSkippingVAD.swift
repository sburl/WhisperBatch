import Foundation

public struct SpeechRegion: Equatable, Sendable {
    public let startSample: Int
    public let endSample: Int

    public init(startSample: Int, endSample: Int) {
        self.startSample = startSample
        self.endSample = endSample
    }
}

public struct SilenceSkippingVAD: Sendable {
    public let frameSampleCount: Int
    public let minimumSpeechFrames: Int
    public let paddingFrames: Int
    public let mergeGapSamples: Int
    public let energyThreshold: Float

    public init(
        sampleRate: Int = AudioConverter.sampleRate,
        frameDuration: TimeInterval = 0.03,
        minimumSpeechDuration: TimeInterval = 0.30,
        paddingDuration: TimeInterval = 0.30,
        // Speech regions separated by a silence gap shorter than this are merged
        // into one clip. Whisper decodes each region independently, so feeding it
        // tiny isolated fragments (e.g. "ask" / "not" split at a brief pause)
        // produces worse text than one contiguous clip with surrounding context.
        // Merging across short gaps keeps dense speech intact while still
        // skipping the long silent stretches this feature targets.
        mergeSilenceGap: TimeInterval = 0.6,
        energyThreshold: Float = 0.01
    ) {
        self.frameSampleCount = max(1, Int(Double(sampleRate) * frameDuration))
        self.minimumSpeechFrames = max(1, Int(ceil(minimumSpeechDuration / frameDuration)))
        self.paddingFrames = max(0, Int(ceil(paddingDuration / frameDuration)))
        self.mergeGapSamples = max(0, Int(Double(sampleRate) * mergeSilenceGap))
        self.energyThreshold = energyThreshold
    }

    public func speechRegions(in samples: [Float]) -> [SpeechRegion] {
        guard !samples.isEmpty else { return [] }

        var speechFrameRanges: [(start: Int, end: Int)] = []
        var currentStart: Int?
        var frameIndex = 0
        var sampleOffset = 0

        while sampleOffset < samples.count {
            let end = min(samples.count, sampleOffset + frameSampleCount)
            let frame = samples[sampleOffset..<end]
            var sumSquares: Float = 0
            for sample in frame {
                sumSquares += sample * sample
            }
            let rms = sqrt(sumSquares / Float(max(1, frame.count)))

            if rms >= energyThreshold {
                if currentStart == nil {
                    currentStart = frameIndex
                }
            } else if let start = currentStart {
                speechFrameRanges.append((start, frameIndex))
                currentStart = nil
            }

            frameIndex += 1
            sampleOffset = end
        }

        if let start = currentStart {
            speechFrameRanges.append((start, frameIndex))
        }

        let padded = speechFrameRanges.compactMap { range -> SpeechRegion? in
            guard range.end - range.start >= minimumSpeechFrames else { return nil }
            let startFrame = max(0, range.start - paddingFrames)
            let endFrame = min(frameIndex, range.end + paddingFrames)
            return SpeechRegion(
                startSample: startFrame * frameSampleCount,
                endSample: min(samples.count, endFrame * frameSampleCount)
            )
        }

        return mergeAdjacent(padded)
    }

    private func mergeAdjacent(_ regions: [SpeechRegion]) -> [SpeechRegion] {
        var merged: [SpeechRegion] = []
        for region in regions {
            guard let last = merged.last else {
                merged.append(region)
                continue
            }
            if region.startSample - last.endSample <= mergeGapSamples {
                merged[merged.count - 1] = SpeechRegion(
                    startSample: last.startSample,
                    endSample: max(last.endSample, region.endSample)
                )
            } else {
                merged.append(region)
            }
        }
        return merged
    }
}
