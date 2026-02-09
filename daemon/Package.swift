// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FlexDaemon",
    platforms: [.macOS(.v13)],
    dependencies: [
        .package(url: "https://github.com/tmandry/AXSwift.git", from: "0.3.2"),
    ],
    targets: [
        .target(
            name: "FlexDaemon",
            dependencies: ["AXSwift"],
            path: "Sources/FlexDaemon"
        ),
        .executableTarget(
            name: "FlexDaemonCLI",
            dependencies: ["FlexDaemon", "AXSwift"],
            path: "Sources/FlexDaemonCLI"
        ),
        .testTarget(
            name: "FlexDaemonTests",
            dependencies: ["FlexDaemon"],
            path: "Tests/FlexDaemonTests"
        ),
    ]
)
