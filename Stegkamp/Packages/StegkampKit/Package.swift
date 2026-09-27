// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "StegkampKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "StegkampKit", targets: ["StegkampKit"])
    ],
    targets: [
        .target(name: "StegkampKit"),
        .testTarget(name: "StegkampKitTests", dependencies: ["StegkampKit"])
    ]
)
