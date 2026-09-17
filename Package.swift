// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "WhisperBatch",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "WhisperBatch", targets: ["WhisperBatch"]),
        .executable(name: "whisperbatch-cli", targets: ["WhisperBatchCLI"]),
        .library(name: "WhisperBatchCore", targets: ["WhisperBatchCore"]),
    ],
    dependencies: [
        .package(url: "https://github.com/argmaxinc/WhisperKit.git", from: "0.9.0"),
        .package(url: "https://github.com/sparkle-project/Sparkle.git", from: "2.6.0"),
    ],
    targets: [
        .target(
            name: "WhisperBatchCore",
            dependencies: [
                .product(name: "WhisperKit", package: "WhisperKit"),
            ],
            path: "Sources/WhisperBatchCore"
        ),
        .executableTarget(
            name: "WhisperBatch",
            dependencies: [
                "WhisperBatchCore",
                .product(name: "Sparkle", package: "Sparkle", condition: .when(platforms: [.macOS])),
            ],
            path: "Sources/WhisperBatch",
            swiftSettings: [
                // APP_STORE flag is passed via -Xswiftc -DAPP_STORE in build.sh
            ],
            linkerSettings: [
                .unsafeFlags(["-Xlinker", "-rpath", "-Xlinker", "@executable_path/../Frameworks"]),
            ]
        ),
        .executableTarget(
            name: "WhisperBatchCLI",
            dependencies: [
                "WhisperBatchCore",
            ],
            path: "Sources/WhisperBatchCLI"
        ),
        .testTarget(
            name: "WhisperBatchTests",
            dependencies: ["WhisperBatchCore", "WhisperBatchCLI"],
            path: "Tests/WhisperBatchTests"
        ),
    ]
)
