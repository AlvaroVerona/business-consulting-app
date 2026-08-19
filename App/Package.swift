// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "BusinessConsultant",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "BusinessConsultant",
            path: "Sources/BusinessConsultant"
        )
    ]
)
