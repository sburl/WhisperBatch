import Foundation

enum HallucinationFilter {
    static let repeatRunThreshold = 3

    static func clean(_ segments: [TranscriptionSegment]) -> [TranscriptionSegment] {
        let kept = segments.compactMap { seg -> TranscriptionSegment? in
            let text = seg.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { return nil }
            guard !isNonSpeechToken(text) else { return nil }
            return TranscriptionSegment(start: seg.start, end: seg.end, text: text)
        }

        var result: [TranscriptionSegment] = []
        var i = 0
        while i < kept.count {
            var j = i + 1
            while j < kept.count, normalized(kept[j].text) == normalized(kept[i].text) {
                j += 1
            }
            let runLength = j - i
            if runLength >= repeatRunThreshold {
                result.append(TranscriptionSegment(
                    start: kept[i].start,
                    end: kept[j - 1].end,
                    text: kept[i].text
                ))
            } else {
                result.append(contentsOf: kept[i..<j])
            }
            i = j
        }
        return result
    }

    static func isNonSpeechToken(_ text: String) -> Bool {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let first = t.first, let last = t.last else { return false }
        let wrapped =
            (first == "[" && last == "]") ||
            (first == "(" && last == ")") ||
            (first == "*" && last == "*") ||
            (first == "♪" || last == "♪")
        if wrapped { return true }

        let speechless = CharacterSet(charactersIn: "♪♫♬-—–_. ")
        return t.unicodeScalars.allSatisfy { speechless.contains($0) }
    }

    static func normalized(_ text: String) -> String {
        text.lowercased()
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .components(separatedBy: .whitespacesAndNewlines)
            .filter { !$0.isEmpty }
            .joined(separator: " ")
    }
}
