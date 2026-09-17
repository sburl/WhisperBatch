import SwiftUI

struct WaveformView: View {
    let peaks: [Float]
    @Binding var startFraction: Double
    @Binding var endFraction: Double

    private let minGap = 0.004

    var body: some View {
        GeometryReader { geo in
            let width = geo.size.width
            let height = geo.size.height

            ZStack(alignment: .topLeading) {
                Canvas { context, size in
                    guard !peaks.isEmpty else { return }
                    let barWidth = size.width / CGFloat(peaks.count)
                    let midY = size.height / 2
                    for (index, peak) in peaks.enumerated() {
                        let fraction = Double(index) / Double(peaks.count)
                        let isSelected = fraction >= startFraction && fraction <= endFraction
                        let barHeight = max(1, CGFloat(peak) * (size.height - 4))
                        let rect = CGRect(
                            x: CGFloat(index) * barWidth,
                            y: midY - barHeight / 2,
                            width: max(0.5, barWidth * 0.7),
                            height: barHeight
                        )
                        context.fill(
                            Path(rect),
                            with: .color(isSelected ? Color.accentColor : Color.secondary.opacity(0.35))
                        )
                    }
                }

                Rectangle()
                    .fill(.black.opacity(0.28))
                    .frame(width: max(0, width * startFraction), height: height)
                Rectangle()
                    .fill(.black.opacity(0.28))
                    .frame(width: max(0, width * (1 - endFraction)), height: height)
                    .offset(x: width * endFraction)

                handle(x: width * startFraction, height: height)
                    .gesture(DragGesture(minimumDistance: 0).onChanged { value in
                        startFraction = min(max(0, value.location.x / width), endFraction - minGap)
                    })
                handle(x: width * endFraction, height: height)
                    .gesture(DragGesture(minimumDistance: 0).onChanged { value in
                        endFraction = max(min(1, value.location.x / width), startFraction + minGap)
                    })
            }
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
    }

    private func handle(x: CGFloat, height: CGFloat) -> some View {
        ZStack {
            Rectangle()
                .fill(Color.accentColor)
                .frame(width: 2)
            Capsule()
                .fill(Color.accentColor)
                .frame(width: 10, height: 28)
                .overlay(
                    Image(systemName: "line.3.horizontal")
                        .font(.system(size: 7, weight: .bold))
                        .rotationEffect(.degrees(90))
                        .foregroundStyle(.white)
                )
        }
        .frame(width: 18, height: height)
        .contentShape(Rectangle())
        .position(x: x, y: height / 2)
    }
}
