// One-off generator for App/Resources/AppIcon.icns — run manually via
// `swift App/Scripts/generate_icon.swift App/Resources` when the icon design
// changes; the result is committed, so this doesn't run on every build.
import AppKit

let sizes: [(name: String, size: Int)] = [
    ("icon_16x16", 16),
    ("icon_16x16@2x", 32),
    ("icon_32x32", 32),
    ("icon_32x32@2x", 64),
    ("icon_128x128", 128),
    ("icon_128x128@2x", 256),
    ("icon_256x256", 256),
    ("icon_256x256@2x", 512),
    ("icon_512x512", 512),
    ("icon_512x512@2x", 1024),
]

let outputRoot = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "."
let iconsetDir = "\(outputRoot)/AppIcon.iconset"
try? FileManager.default.createDirectory(atPath: iconsetDir, withIntermediateDirectories: true)

func drawIcon(size: Int) -> NSImage {
    let image = NSImage(size: NSSize(width: size, height: size))
    image.lockFocus()

    let rect = NSRect(x: 0, y: 0, width: size, height: size)
    let cornerRadius = CGFloat(size) * 0.22
    let path = NSBezierPath(roundedRect: rect, xRadius: cornerRadius, yRadius: cornerRadius)
    path.addClip()

    let gradient = NSGradient(colors: [
        NSColor(calibratedRed: 0.11, green: 0.28, blue: 0.52, alpha: 1.0),
        NSColor(calibratedRed: 0.05, green: 0.56, blue: 0.53, alpha: 1.0),
    ])
    gradient?.draw(in: path, angle: -45)

    if let symbolImage = NSImage(systemSymbolName: "chart.line.uptrend.xyaxis", accessibilityDescription: nil) {
        let sizeConfig = NSImage.SymbolConfiguration(pointSize: CGFloat(size) * 0.48, weight: .semibold)
        let colorConfig = NSImage.SymbolConfiguration(paletteColors: [NSColor.white])
        let config = sizeConfig.applying(colorConfig)
        let configured = symbolImage.withSymbolConfiguration(config) ?? symbolImage

        let symbolSize = configured.size
        let symbolRect = NSRect(
            x: (CGFloat(size) - symbolSize.width) / 2,
            y: (CGFloat(size) - symbolSize.height) / 2,
            width: symbolSize.width,
            height: symbolSize.height
        )
        configured.draw(in: symbolRect)
    }

    image.unlockFocus()
    return image
}

for entry in sizes {
    let image = drawIcon(size: entry.size)
    guard let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff),
          let png = bitmap.representation(using: .png, properties: [:]) else {
        print("Failed to render \(entry.name)")
        continue
    }
    let path = "\(iconsetDir)/\(entry.name).png"
    try? png.write(to: URL(fileURLWithPath: path))
    print("Wrote \(path)")
}

print("Now run: iconutil -c icns \(iconsetDir) -o \(outputRoot)/AppIcon.icns")
