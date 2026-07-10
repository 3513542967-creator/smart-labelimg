# Native Foundation and Safe I/O Implementation Plan

> **Superseded:** Do not execute this plan. The product direction changed to incremental PySide6 development for a macOS Apple Silicon GitHub release. See `docs/superpowers/specs/2026-07-10-smart-labelimg-github-macos-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable native macOS foundation that discovers image folders, reads and writes LabelImg-compatible YOLO/VOC annotations, protects YOLO class IDs, retains sandbox folder access, and saves without silent data loss.

**Architecture:** Add a SwiftPM workspace under `macos/` without disturbing the existing Python application. `AnnotationCore` owns format-neutral value types, `DatasetIO` owns formats and directory mapping, `SaveSystem` owns serialized disk mutation and recovery, and a minimal SwiftUI executable proves the modules together before the high-performance canvas is added.

**Tech Stack:** Swift 6, SwiftUI, AppKit, ImageIO, FoundationXML, CryptoKit, XCTest, Swift Package Manager; Apple Silicon and macOS 14 or later.

## Global Constraints

- Support Apple Silicon only and macOS 14 or later.
- Keep the existing Python/PySide6 application unchanged as a behavior reference.
- Support axis-aligned rectangular boxes, YOLO detection TXT, and Pascal VOC XML only.
- Do not create a proprietary project file or copy/move source images.
- Default the annotation directory to the image directory and map labels by image basename.
- Keep all processing local and require no account, network connection, Python installation, or model download.
- Use user-selected security-scoped bookmarks for persistent folder access.
- Auto-save is enabled by default, but no UI component may write annotation files directly.
- Treat `classes.txt` ordering as locked dataset schema after existing YOLO annotations are detected or the first annotation is saved.
- Store recovery data in Application Support, never in the user's dataset directory.
- Use English identifiers and localized user-facing strings; Simplified Chinese localization is added in the manual-annotator plan.
- Run every filesystem, image-decoding, and serialization operation off the main actor.
- The current machine has Swift 6.3.2 command-line tools but no selected full Xcode installation; this plan must pass with `swift test`. Xcode app archiving is part of the distribution-readiness plan.

---

## Planned File Structure

```text
macos/
  Package.swift                              SwiftPM products and targets
  Sources/
    AnnotationCore/
      ImageSize.swift                        Positive image dimensions
      BoundingBox.swift                      Format-neutral rectangle model
      AnnotationDocument.swift               Per-image annotation state
    DatasetIO/
      AnnotationFormat.swift                 YOLO/VOC selection and suffixes
      AnnotationDiagnostic.swift             Structured parser diagnostics
      AnnotationStore.swift                  Store protocol and load result
      YOLOStore.swift                        YOLO parser and serializer
      VOCStore.swift                         VOC parser and serializer
      ClassCatalog.swift                     Ordered class schema and mapping
      DatasetSession.swift                   Image discovery and path mapping
      BookmarkStore.swift                    Security-scoped folder bookmarks
    SaveSystem/
      FileFingerprint.swift                  External-change fingerprint
      RecoveryStore.swift                    Application Support snapshots
      SaveCoordinator.swift                  Atomic, serialized save actor
    SmartLabelImgApp/
      SmartLabelImgApp.swift                 Native executable entry point
      AppModel.swift                         Main-actor session coordinator
      WelcomeView.swift                      Folder-opening empty state
      DatasetView.swift                      Minimal list/summary/save UI
  Resources/
    AppIcon-1024.png                         Generated source artwork
    AppIcon.iconset/                         Standard macOS icon renditions
    AppIcon.icns                             Bundle icon
  Tests/
    AnnotationCoreTests/AnnotationCoreTests.swift
    DatasetIOTests/YOLOStoreTests.swift
    DatasetIOTests/VOCStoreTests.swift
    DatasetIOTests/DatasetSessionTests.swift
    DatasetIOTests/ClassCatalogTests.swift
    SaveSystemTests/SaveCoordinatorTests.swift
    IntegrationTests/DatasetRoundTripTests.swift
script/build_and_run.sh                      Canonical build, bundle, launch, and verify entrypoint
.codex/environments/environment.toml         Codex Run action
docs/native-development.md                  Native build and test instructions
```

The later canvas, SAM, propagation, and distribution plans add new modules rather than expanding these files beyond their listed responsibilities.

### Task 1: Swift Package and Annotation Core

**Files:**
- Create: `macos/Package.swift`
- Create: `macos/Sources/AnnotationCore/ImageSize.swift`
- Create: `macos/Sources/AnnotationCore/BoundingBox.swift`
- Create: `macos/Sources/AnnotationCore/AnnotationDocument.swift`
- Create: `macos/Tests/AnnotationCoreTests/AnnotationCoreTests.swift`

**Interfaces:**
- Consumes: No earlier implementation tasks.
- Produces: `ImageSize.init(width:height:) throws`, `BoundingBox.init(id:className:xMin:yMin:xMax:yMax:isDifficult:)`, `BoundingBox.clamped(to:)`, and `AnnotationDocument.init(imageURL:imageSize:boxes:isVerified:)`.

- [ ] **Step 1: Create the package manifest and write failing core-model tests**

```swift
// macos/Package.swift
// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SmartLabelImg",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "AnnotationCore", targets: ["AnnotationCore"]),
    ],
    targets: [
        .target(name: "AnnotationCore"),
        .testTarget(name: "AnnotationCoreTests", dependencies: ["AnnotationCore"]),
    ]
)
```

```swift
// macos/Tests/AnnotationCoreTests/AnnotationCoreTests.swift
import XCTest
@testable import AnnotationCore

final class AnnotationCoreTests: XCTestCase {
    func testImageSizeRejectsNonPositiveDimensions() {
        XCTAssertThrowsError(try ImageSize(width: 0, height: 1080))
        XCTAssertNoThrow(try ImageSize(width: 1920, height: 1080))
    }

    func testBoxNormalizesAndClampsToImage() throws {
        let size = try ImageSize(width: 100, height: 80)
        let box = BoundingBox(className: "car", xMin: 120, yMin: 60, xMax: -10, yMax: 90)
        XCTAssertEqual(box.clamped(to: size), BoundingBox(
            id: box.id, className: "car", xMin: 0, yMin: 60, xMax: 99, yMax: 79
        ))
    }

    func testDocumentRejectsZeroAreaBoxes() throws {
        let size = try ImageSize(width: 100, height: 80)
        let document = AnnotationDocument(
            imageURL: URL(fileURLWithPath: "/tmp/a.jpg"),
            imageSize: size,
            boxes: [BoundingBox(className: "car", xMin: 2, yMin: 3, xMax: 2, yMax: 20)]
        )
        XCTAssertEqual(document.validBoxes.count, 0)
    }
}
```

- [ ] **Step 2: Run the focused tests and verify the expected compile failure**

Run: `cd macos && swift test --filter AnnotationCoreTests`

Expected: FAIL because `ImageSize`, `BoundingBox`, and `AnnotationDocument` do not exist.

- [ ] **Step 3: Implement the format-neutral annotation types**

```swift
// macos/Sources/AnnotationCore/ImageSize.swift
import Foundation

public enum AnnotationValidationError: Error, Equatable, Sendable {
    case invalidImageSize(width: Int, height: Int)
    case emptyClassName
}

public struct ImageSize: Codable, Equatable, Sendable {
    public let width: Int
    public let height: Int

    public init(width: Int, height: Int) throws {
        guard width > 0, height > 0 else {
            throw AnnotationValidationError.invalidImageSize(width: width, height: height)
        }
        self.width = width
        self.height = height
    }
}
```

```swift
// macos/Sources/AnnotationCore/BoundingBox.swift
import Foundation

public struct BoundingBox: Identifiable, Codable, Equatable, Sendable {
    public let id: UUID
    public var className: String
    public var xMin: Double
    public var yMin: Double
    public var xMax: Double
    public var yMax: Double
    public var isDifficult: Bool

    public init(
        id: UUID = UUID(), className: String,
        xMin: Double, yMin: Double, xMax: Double, yMax: Double,
        isDifficult: Bool = false
    ) {
        self.id = id
        self.className = className
        self.xMin = min(xMin, xMax)
        self.yMin = min(yMin, yMax)
        self.xMax = max(xMin, xMax)
        self.yMax = max(yMin, yMax)
        self.isDifficult = isDifficult
    }

    public var width: Double { max(0, xMax - xMin) }
    public var height: Double { max(0, yMax - yMin) }
    public var hasArea: Bool { width > 0 && height > 0 }

    public func clamped(to size: ImageSize) -> BoundingBox {
        BoundingBox(
            id: id, className: className,
            xMin: min(max(0, xMin), Double(size.width - 1)),
            yMin: min(max(0, yMin), Double(size.height - 1)),
            xMax: min(max(0, xMax), Double(size.width - 1)),
            yMax: min(max(0, yMax), Double(size.height - 1)),
            isDifficult: isDifficult
        )
    }
}
```

```swift
// macos/Sources/AnnotationCore/AnnotationDocument.swift
import Foundation

public struct AnnotationDocument: Codable, Equatable, Sendable {
    public let imageURL: URL
    public let imageSize: ImageSize
    public var boxes: [BoundingBox]
    public var isVerified: Bool

    public init(
        imageURL: URL, imageSize: ImageSize,
        boxes: [BoundingBox] = [], isVerified: Bool = false
    ) {
        self.imageURL = imageURL
        self.imageSize = imageSize
        self.boxes = boxes
        self.isVerified = isVerified
    }

    public var validBoxes: [BoundingBox] {
        boxes.map { $0.clamped(to: imageSize) }
            .filter { $0.hasArea && !$0.className.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }
}
```

- [ ] **Step 4: Run core tests and the complete package test suite**

Run: `cd macos && swift test --filter AnnotationCoreTests && swift test`

Expected: PASS, with 3 focused tests and no failures in the complete suite.

- [ ] **Step 5: Commit the core foundation**

```bash
git add macos/Package.swift macos/Sources/AnnotationCore macos/Tests/AnnotationCoreTests
git commit -m "feat(macOS): add annotation core models"
```

### Task 2: YOLO Store and Diagnostics

**Files:**
- Modify: `macos/Package.swift`
- Create: `macos/Sources/DatasetIO/AnnotationDiagnostic.swift`
- Create: `macos/Sources/DatasetIO/AnnotationStore.swift`
- Create: `macos/Sources/DatasetIO/YOLOStore.swift`
- Create: `macos/Tests/DatasetIOTests/YOLOStoreTests.swift`

**Interfaces:**
- Consumes: `ImageSize`, `BoundingBox`, and `AnnotationDocument` from Task 1.
- Produces: `AnnotationStore`, `AnnotationLoadResult`, and `YOLOStore.load(data:imageURL:imageSize:classes:)` / `YOLOStore.serialize(document:classes:)`.

- [ ] **Step 1: Add DatasetIO targets and write failing YOLO compatibility and diagnostic tests**

Add the DatasetIO product to `products` in `macos/Package.swift`:

```swift
.library(name: "DatasetIO", targets: ["DatasetIO"]),
```

Add these entries to `targets`:

```swift
.target(name: "DatasetIO", dependencies: ["AnnotationCore"]),
.testTarget(name: "DatasetIOTests", dependencies: ["AnnotationCore", "DatasetIO"]),
```

Create the source-directory marker that makes the still-incomplete target discoverable:

```swift
// macos/Sources/DatasetIO/AnnotationDiagnostic.swift
import Foundation
```

```swift
// macos/Tests/DatasetIOTests/YOLOStoreTests.swift
import XCTest
import AnnotationCore
@testable import DatasetIO

final class YOLOStoreTests: XCTestCase {
    func testLoadsAndSerializesLabelImgYOLO() throws {
        let size = try ImageSize(width: 200, height: 100)
        let source = Data("1 0.500000 0.500000 0.200000 0.400000\n".utf8)
        let result = try YOLOStore().load(
            data: source, imageURL: URL(fileURLWithPath: "/tmp/a.jpg"),
            imageSize: size, classes: ["person", "car"]
        )
        XCTAssertTrue(result.diagnostics.isEmpty)
        XCTAssertEqual(result.document.boxes[0].className, "car")
        XCTAssertEqual(result.document.boxes[0].xMin, 80, accuracy: 0.0001)
        XCTAssertEqual(String(decoding: try YOLOStore().serialize(
            document: result.document, classes: ["person", "car"]
        ), as: UTF8.self), "1 0.500000 0.500000 0.200000 0.400000\n")
    }

    func testUnknownClassIDIsBlockingDiagnostic() throws {
        let result = try YOLOStore().load(
            data: Data("9 0.5 0.5 0.2 0.2\n".utf8),
            imageURL: URL(fileURLWithPath: "/tmp/a.jpg"),
            imageSize: try ImageSize(width: 100, height: 100), classes: ["car"]
        )
        XCTAssertEqual(result.document.boxes, [])
        XCTAssertEqual(result.diagnostics.first?.severity, .blocking)
        XCTAssertEqual(result.diagnostics.first?.line, 1)
    }

    func testEmptyDocumentSerializesAsEmptyFile() throws {
        let document = AnnotationDocument(
            imageURL: URL(fileURLWithPath: "/tmp/a.jpg"),
            imageSize: try ImageSize(width: 100, height: 100)
        )
        XCTAssertEqual(try YOLOStore().serialize(document: document, classes: ["car"]), Data())
    }
}
```

- [ ] **Step 2: Run tests and verify missing-store failure**

Run: `cd macos && swift test --filter YOLOStoreTests`

Expected: FAIL because `YOLOStore`, `AnnotationLoadResult`, and `AnnotationDiagnostic` do not exist.

- [ ] **Step 3: Implement diagnostics, the store protocol, and YOLO parsing/serialization**

```swift
// macos/Sources/DatasetIO/AnnotationDiagnostic.swift
import Foundation

public enum DiagnosticSeverity: String, Codable, Equatable, Sendable {
    case warning
    case blocking
}

public struct AnnotationDiagnostic: Codable, Equatable, Sendable {
    public let severity: DiagnosticSeverity
    public let message: String
    public let line: Int?

    public init(severity: DiagnosticSeverity, message: String, line: Int? = nil) {
        self.severity = severity
        self.message = message
        self.line = line
    }
}
```

```swift
// macos/Sources/DatasetIO/AnnotationStore.swift
import Foundation
import AnnotationCore

public struct AnnotationLoadResult: Equatable, Sendable {
    public let document: AnnotationDocument
    public let diagnostics: [AnnotationDiagnostic]

    public init(document: AnnotationDocument, diagnostics: [AnnotationDiagnostic]) {
        self.document = document
        self.diagnostics = diagnostics
    }
}

public protocol AnnotationStore: Sendable {
    func load(data: Data, imageURL: URL, imageSize: ImageSize, classes: [String]) throws -> AnnotationLoadResult
    func serialize(document: AnnotationDocument, classes: [String]) throws -> Data
}

public enum AnnotationStoreError: Error, Equatable, Sendable {
    case unknownClass(String)
    case invalidClassCatalog
    case invalidXML(String)
}
```

```swift
// macos/Sources/DatasetIO/YOLOStore.swift
import Foundation
import AnnotationCore

public struct YOLOStore: AnnotationStore {
    public init() {}

    public func load(
        data: Data, imageURL: URL, imageSize: ImageSize, classes: [String]
    ) throws -> AnnotationLoadResult {
        let text = String(decoding: data, as: UTF8.self)
        var boxes: [BoundingBox] = []
        var diagnostics: [AnnotationDiagnostic] = []

        for (offset, rawLine) in text.split(separator: "\n", omittingEmptySubsequences: false).enumerated() {
            let lineNumber = offset + 1
            let fields = rawLine.split(whereSeparator: { $0.isWhitespace })
            if fields.isEmpty { continue }
            guard fields.count == 5,
                  let classID = Int(fields[0]),
                  let centerX = Double(fields[1]), let centerY = Double(fields[2]),
                  let width = Double(fields[3]), let height = Double(fields[4]),
                  centerX.isFinite, centerY.isFinite, width.isFinite, height.isFinite,
                  width > 0, height > 0 else {
                diagnostics.append(.init(severity: .blocking, message: "Invalid YOLO row", line: lineNumber))
                continue
            }
            guard classes.indices.contains(classID) else {
                diagnostics.append(.init(severity: .blocking, message: "Unknown class ID \(classID)", line: lineNumber))
                continue
            }
            let pixelWidth = width * Double(imageSize.width)
            let pixelHeight = height * Double(imageSize.height)
            boxes.append(BoundingBox(
                className: classes[classID],
                xMin: centerX * Double(imageSize.width) - pixelWidth / 2,
                yMin: centerY * Double(imageSize.height) - pixelHeight / 2,
                xMax: centerX * Double(imageSize.width) + pixelWidth / 2,
                yMax: centerY * Double(imageSize.height) + pixelHeight / 2
            ).clamped(to: imageSize))
        }
        return AnnotationLoadResult(
            document: AnnotationDocument(imageURL: imageURL, imageSize: imageSize, boxes: boxes),
            diagnostics: diagnostics
        )
    }

    public func serialize(document: AnnotationDocument, classes: [String]) throws -> Data {
        guard Set(classes).count == classes.count,
              classes.allSatisfy({ !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }) else {
            throw AnnotationStoreError.invalidClassCatalog
        }
        var rows: [String] = []
        for box in document.validBoxes {
            guard let classID = classes.firstIndex(of: box.className) else {
                throw AnnotationStoreError.unknownClass(box.className)
            }
            let width = box.width / Double(document.imageSize.width)
            let height = box.height / Double(document.imageSize.height)
            let centerX = ((box.xMin + box.xMax) / 2) / Double(document.imageSize.width)
            let centerY = ((box.yMin + box.yMax) / 2) / Double(document.imageSize.height)
            rows.append(String(format: "%d %.6f %.6f %.6f %.6f", classID, centerX, centerY, width, height))
        }
        return rows.isEmpty ? Data() : Data((rows.joined(separator: "\n") + "\n").utf8)
    }
}
```

- [ ] **Step 4: Run YOLO and full tests**

Run: `cd macos && swift test --filter YOLOStoreTests && swift test`

Expected: PASS, including exact six-decimal LabelImg-compatible output and blocking unknown-ID diagnostics.

- [ ] **Step 5: Commit the YOLO store**

```bash
git add macos/Sources/DatasetIO macos/Tests/DatasetIOTests/YOLOStoreTests.swift
git commit -m "feat(macOS): add YOLO annotation store"
```

### Task 3: Pascal VOC Store

**Files:**
- Create: `macos/Sources/DatasetIO/VOCStore.swift`
- Create: `macos/Tests/DatasetIOTests/VOCStoreTests.swift`

**Interfaces:**
- Consumes: `AnnotationStore`, `AnnotationLoadResult`, `AnnotationDiagnostic`, and `AnnotationCore` models.
- Produces: `VOCStore.load(data:imageURL:imageSize:classes:)` and `VOCStore.serialize(document:classes:)` with LabelImg-compatible `verified` and `difficult` fields.

- [ ] **Step 1: Write failing VOC round-trip and empty-document tests**

```swift
// macos/Tests/DatasetIOTests/VOCStoreTests.swift
import XCTest
import FoundationXML
import AnnotationCore
@testable import DatasetIO

final class VOCStoreTests: XCTestCase {
    func testLoadsDifficultAndVerified() throws {
        let xml = """
        <?xml version="1.0" encoding="utf-8"?>
        <annotation verified="yes"><filename>a.jpg</filename><size><width>100</width><height>80</height><depth>3</depth></size><object><name>car</name><pose>Unspecified</pose><truncated>0</truncated><difficult>1</difficult><bndbox><xmin>10</xmin><ymin>12</ymin><xmax>50</xmax><ymax>60</ymax></bndbox></object></annotation>
        """
        let result = try VOCStore().load(
            data: Data(xml.utf8), imageURL: URL(fileURLWithPath: "/tmp/a.jpg"),
            imageSize: try ImageSize(width: 100, height: 80), classes: []
        )
        XCTAssertTrue(result.document.isVerified)
        XCTAssertTrue(result.document.boxes[0].isDifficult)
        XCTAssertEqual(result.document.boxes[0].className, "car")
    }

    func testSerializesValidEmptyVOC() throws {
        let document = AnnotationDocument(
            imageURL: URL(fileURLWithPath: "/tmp/a.jpg"),
            imageSize: try ImageSize(width: 100, height: 80)
        )
        let data = try VOCStore().serialize(document: document, classes: [])
        let xml = try XMLDocument(data: data)
        XCTAssertEqual(try xml.nodes(forXPath: "/annotation/object").count, 0)
        XCTAssertEqual(try xml.nodes(forXPath: "/annotation/filename").first?.stringValue, "a.jpg")
    }
}
```

- [ ] **Step 2: Run tests and verify `VOCStore` is missing**

Run: `cd macos && swift test --filter VOCStoreTests`

Expected: FAIL with `cannot find 'VOCStore' in scope`.

- [ ] **Step 3: Implement DOM-based VOC loading and serialization**

```swift
// macos/Sources/DatasetIO/VOCStore.swift
import Foundation
import FoundationXML
import AnnotationCore

public struct VOCStore: AnnotationStore {
    public init() {}

    public func load(
        data: Data, imageURL: URL, imageSize: ImageSize, classes: [String]
    ) throws -> AnnotationLoadResult {
        let xml: XMLDocument
        do { xml = try XMLDocument(data: data, options: [.nodePreserveAll]) }
        catch { throw AnnotationStoreError.invalidXML(error.localizedDescription) }
        guard let root = xml.rootElement(), root.name == "annotation" else {
            throw AnnotationStoreError.invalidXML("Missing annotation root")
        }
        let verified = root.attribute(forName: "verified")?.stringValue?.lowercased() == "yes"
        var boxes: [BoundingBox] = []
        var diagnostics: [AnnotationDiagnostic] = []
        for (index, node) in (try root.nodes(forXPath: "object")).enumerated() {
            guard let object = node as? XMLElement,
                  let name = try object.nodes(forXPath: "name").first?.stringValue?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !name.isEmpty,
                  let xMin = Double(try object.nodes(forXPath: "bndbox/xmin").first?.stringValue ?? ""),
                  let yMin = Double(try object.nodes(forXPath: "bndbox/ymin").first?.stringValue ?? ""),
                  let xMax = Double(try object.nodes(forXPath: "bndbox/xmax").first?.stringValue ?? ""),
                  let yMax = Double(try object.nodes(forXPath: "bndbox/ymax").first?.stringValue ?? "") else {
                diagnostics.append(.init(severity: .blocking, message: "Invalid VOC object \(index + 1)"))
                continue
            }
            let difficult = (try object.nodes(forXPath: "difficult").first?.stringValue ?? "0") == "1"
            let box = BoundingBox(
                className: name, xMin: xMin, yMin: yMin, xMax: xMax, yMax: yMax,
                isDifficult: difficult
            ).clamped(to: imageSize)
            if box.hasArea { boxes.append(box) }
            else { diagnostics.append(.init(severity: .blocking, message: "Zero-area VOC object \(index + 1)")) }
        }
        return AnnotationLoadResult(
            document: AnnotationDocument(
                imageURL: imageURL, imageSize: imageSize, boxes: boxes, isVerified: verified
            ),
            diagnostics: diagnostics
        )
    }

    public func serialize(document: AnnotationDocument, classes: [String]) throws -> Data {
        let root = XMLElement(name: "annotation")
        if document.isVerified { root.addAttribute(XMLNode.attribute(withName: "verified", stringValue: "yes") as! XMLNode) }
        root.addChild(XMLElement(name: "folder", stringValue: document.imageURL.deletingLastPathComponent().lastPathComponent))
        root.addChild(XMLElement(name: "filename", stringValue: document.imageURL.lastPathComponent))
        root.addChild(XMLElement(name: "path", stringValue: document.imageURL.path))
        let size = XMLElement(name: "size")
        size.addChild(XMLElement(name: "width", stringValue: String(document.imageSize.width)))
        size.addChild(XMLElement(name: "height", stringValue: String(document.imageSize.height)))
        size.addChild(XMLElement(name: "depth", stringValue: "3"))
        root.addChild(size)
        root.addChild(XMLElement(name: "segmented", stringValue: "0"))
        for box in document.validBoxes {
            let object = XMLElement(name: "object")
            object.addChild(XMLElement(name: "name", stringValue: box.className))
            object.addChild(XMLElement(name: "pose", stringValue: "Unspecified"))
            object.addChild(XMLElement(name: "truncated", stringValue: "0"))
            object.addChild(XMLElement(name: "difficult", stringValue: box.isDifficult ? "1" : "0"))
            let bounds = XMLElement(name: "bndbox")
            bounds.addChild(XMLElement(name: "xmin", stringValue: String(Int(box.xMin.rounded()))))
            bounds.addChild(XMLElement(name: "ymin", stringValue: String(Int(box.yMin.rounded()))))
            bounds.addChild(XMLElement(name: "xmax", stringValue: String(Int(box.xMax.rounded()))))
            bounds.addChild(XMLElement(name: "ymax", stringValue: String(Int(box.yMax.rounded()))))
            object.addChild(bounds)
            root.addChild(object)
        }
        let documentNode = XMLDocument(rootElement: root)
        documentNode.version = "1.0"
        documentNode.characterEncoding = "utf-8"
        return documentNode.xmlData(options: [.nodePrettyPrint])
    }
}
```

- [ ] **Step 4: Run VOC and full tests**

Run: `cd macos && swift test --filter VOCStoreTests && swift test`

Expected: PASS, including empty VOC, difficult, and verified behavior.

- [ ] **Step 5: Commit the VOC store**

```bash
git add macos/Sources/DatasetIO/VOCStore.swift macos/Tests/DatasetIOTests/VOCStoreTests.swift
git commit -m "feat(macOS): add Pascal VOC annotation store"
```

### Task 4: Dataset Discovery, Class Catalog, and Sandbox Bookmarks

**Files:**
- Create: `macos/Sources/DatasetIO/AnnotationFormat.swift`
- Create: `macos/Sources/DatasetIO/ClassCatalog.swift`
- Create: `macos/Sources/DatasetIO/DatasetSession.swift`
- Create: `macos/Sources/DatasetIO/BookmarkStore.swift`
- Create: `macos/Tests/DatasetIOTests/ClassCatalogTests.swift`
- Create: `macos/Tests/DatasetIOTests/DatasetSessionTests.swift`

**Interfaces:**
- Consumes: Annotation stores and core models from Tasks 1–3.
- Produces: `AnnotationFormat`, `ClassCatalog`, `DatasetSession.discover(imageDirectory:annotationDirectory:format:fileManager:)`, `DatasetSession.annotationURL(for:)`, and `BookmarkStore.save(url:key:)` / `BookmarkStore.resolve(key:)`.

- [ ] **Step 1: Write failing discovery, collision, catalog-lock, and bookmark tests**

```swift
// macos/Tests/DatasetIOTests/DatasetSessionTests.swift
import XCTest
@testable import DatasetIO

final class DatasetSessionTests: XCTestCase {
    func testDiscoversTopLevelImagesAndMapsSeparateAnnotationFolder() throws {
        let root = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        let images = root.appending(path: "images", directoryHint: .isDirectory)
        let labels = root.appending(path: "labels", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: images, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: labels, withIntermediateDirectories: true)
        try Data().write(to: images.appending(path: "b.png"))
        try Data().write(to: images.appending(path: "a.jpg"))
        let session = try DatasetSession.discover(
            imageDirectory: images, annotationDirectory: labels, format: .yolo
        )
        XCTAssertEqual(session.images.map(\.lastPathComponent), ["a.jpg", "b.png"])
        XCTAssertEqual(session.annotationURL(for: session.images[0]), labels.appending(path: "a.txt"))
        try Data("car\n".utf8).write(to: images.appending(path: "classes.txt"))
        XCTAssertEqual(session.readableClassesURL(), images.appending(path: "classes.txt"))
    }

    func testDuplicateBasenameBlocksSession() throws {
        let directory = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try Data().write(to: directory.appending(path: "same.jpg"))
        try Data().write(to: directory.appending(path: "same.png"))
        XCTAssertThrowsError(try DatasetSession.discover(
            imageDirectory: directory, annotationDirectory: directory, format: .yolo
        )) { XCTAssertEqual($0 as? DatasetSessionError, .duplicateBasename("same")) }
    }
}
```

```swift
// macos/Tests/DatasetIOTests/ClassCatalogTests.swift
import XCTest
@testable import DatasetIO

final class ClassCatalogTests: XCTestCase {
    func testLockedCatalogOnlyAppends() throws {
        var catalog = try ClassCatalog(names: ["person", "car"], isLocked: true)
        try catalog.append("truck")
        XCTAssertEqual(catalog.names, ["person", "car", "truck"])
        XCTAssertThrowsError(try catalog.replaceNames(["car", "person", "truck"]))
        XCTAssertEqual(catalog.serialized, Data("person\ncar\ntruck\n".utf8))
    }
}
```

- [ ] **Step 2: Run tests and verify missing dataset types**

Run: `cd macos && swift test --filter 'DatasetSessionTests|ClassCatalogTests'`

Expected: FAIL because dataset and catalog types are undefined.

- [ ] **Step 3: Implement formats, deterministic discovery, collision protection, and class locking**

```swift
// macos/Sources/DatasetIO/AnnotationFormat.swift
import Foundation

public enum AnnotationFormat: String, Codable, CaseIterable, Sendable {
    case yolo
    case pascalVOC

    public var annotationExtension: String { self == .yolo ? "txt" : "xml" }
}
```

```swift
// macos/Sources/DatasetIO/ClassCatalog.swift
import Foundation

public enum ClassCatalogError: Error, Equatable, Sendable {
    case emptyName
    case duplicateName(String)
    case lockedOrder
}

public struct ClassCatalog: Codable, Equatable, Sendable {
    public private(set) var names: [String]
    public private(set) var isLocked: Bool

    public init(names: [String], isLocked: Bool) throws {
        let cleaned = names.map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        guard cleaned.allSatisfy({ !$0.isEmpty }) else { throw ClassCatalogError.emptyName }
        guard Set(cleaned).count == cleaned.count else {
            throw ClassCatalogError.duplicateName(cleaned.first { name in cleaned.filter { $0 == name }.count > 1 }!)
        }
        self.names = cleaned
        self.isLocked = isLocked
    }

    public init(data: Data, isLocked: Bool) throws {
        try self.init(
            names: String(decoding: data, as: UTF8.self).split(whereSeparator: \.isNewline).map(String.init),
            isLocked: isLocked
        )
    }

    public mutating func append(_ name: String) throws {
        let cleaned = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { throw ClassCatalogError.emptyName }
        guard !names.contains(cleaned) else { throw ClassCatalogError.duplicateName(cleaned) }
        names.append(cleaned)
    }

    public mutating func replaceNames(_ replacement: [String]) throws {
        if isLocked && replacement != names { throw ClassCatalogError.lockedOrder }
        self = try ClassCatalog(names: replacement, isLocked: isLocked)
    }

    public mutating func lock() { isLocked = true }
    public var serialized: Data { names.isEmpty ? Data() : Data((names.joined(separator: "\n") + "\n").utf8) }
}
```

```swift
// macos/Sources/DatasetIO/DatasetSession.swift
import Foundation

public enum DatasetSessionError: Error, Equatable, Sendable {
    case notDirectory
    case duplicateBasename(String)
}

public struct DatasetSession: Equatable, Sendable {
    public let imageDirectory: URL
    public let annotationDirectory: URL
    public let format: AnnotationFormat
    public let images: [URL]

    private static let supportedExtensions: Set<String> = [
        "jpg", "jpeg", "png", "tif", "tiff", "bmp", "heic", "webp"
    ]

    public static func discover(
        imageDirectory: URL, annotationDirectory: URL,
        format: AnnotationFormat, fileManager: FileManager = .default
    ) throws -> DatasetSession {
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: imageDirectory.path, isDirectory: &isDirectory), isDirectory.boolValue else {
            throw DatasetSessionError.notDirectory
        }
        let contents = try fileManager.contentsOfDirectory(
            at: imageDirectory, includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        )
        let images = contents.filter { supportedExtensions.contains($0.pathExtension.lowercased()) }
            .sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
        var basenames = Set<String>()
        for image in images {
            let basename = image.deletingPathExtension().lastPathComponent
            guard basenames.insert(basename).inserted else { throw DatasetSessionError.duplicateBasename(basename) }
        }
        return DatasetSession(
            imageDirectory: imageDirectory, annotationDirectory: annotationDirectory,
            format: format, images: images
        )
    }

    public func annotationURL(for imageURL: URL) -> URL {
        annotationDirectory.appending(path: imageURL.deletingPathExtension().lastPathComponent)
            .appendingPathExtension(format.annotationExtension)
    }

    public var classesURL: URL { annotationDirectory.appending(path: "classes.txt") }

    public func readableClassesURL(fileManager: FileManager = .default) -> URL? {
        if fileManager.fileExists(atPath: classesURL.path) { return classesURL }
        let imageClasses = imageDirectory.appending(path: "classes.txt")
        return fileManager.fileExists(atPath: imageClasses.path) ? imageClasses : nil
    }
}
```

- [ ] **Step 4: Implement bookmark persistence and add a round-trip test using a temporary folder**

```swift
// macos/Sources/DatasetIO/BookmarkStore.swift
import Foundation

public enum BookmarkStoreError: Error, Sendable { case staleBookmark }

public struct BookmarkStore: @unchecked Sendable {
    private let defaults: UserDefaults
    public init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    public func save(url: URL, key: String) throws {
        let data = try url.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil, relativeTo: nil)
        defaults.set(data, forKey: key)
    }

    public func resolve(key: String) throws -> URL? {
        guard let data = defaults.data(forKey: key) else { return nil }
        var stale = false
        let url = try URL(
            resolvingBookmarkData: data, options: [.withSecurityScope],
            relativeTo: nil, bookmarkDataIsStale: &stale
        )
        guard !stale else { throw BookmarkStoreError.staleBookmark }
        return url
    }
}
```

Add this test to `DatasetSessionTests.swift`:

```swift
func testBookmarkRoundTrip() throws {
    let suite = "BookmarkStoreTests.\(UUID().uuidString)"
    let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
    defer { defaults.removePersistentDomain(forName: suite) }
    let store = BookmarkStore(defaults: defaults)
    let url = FileManager.default.temporaryDirectory
    try store.save(url: url, key: "images")
    XCTAssertEqual(try store.resolve(key: "images")?.standardizedFileURL, url.standardizedFileURL)
}
```

- [ ] **Step 5: Run all DatasetIO tests**

Run: `cd macos && swift test --filter DatasetIOTests && swift test`

Expected: PASS with deterministic sorting, collision rejection, locked class order, and bookmark round trip.

- [ ] **Step 6: Commit dataset session infrastructure**

```bash
git add macos/Sources/DatasetIO macos/Tests/DatasetIOTests
git commit -m "feat(macOS): add dataset discovery and class schema"
```

### Task 5: Atomic Save, Conflict Detection, and Recovery

**Files:**
- Modify: `macos/Package.swift`
- Create: `macos/Sources/SaveSystem/FileFingerprint.swift`
- Create: `macos/Sources/SaveSystem/RecoveryStore.swift`
- Create: `macos/Sources/SaveSystem/SaveCoordinator.swift`
- Create: `macos/Tests/SaveSystemTests/SaveCoordinatorTests.swift`

**Interfaces:**
- Consumes: Serialized `Data`, `AnnotationDocument`, and dataset destination URLs.
- Produces: `FileFingerprint.capture(url:)`, `SaveRequest`, `SaveOutcome`, `RecoveryStore`, and actor method `SaveCoordinator.save(_:) async throws -> SaveOutcome`.

- [ ] **Step 1: Add SaveSystem targets and write failing save, conflict, rollback, and recovery tests**

Add the SaveSystem product to `products` in `macos/Package.swift`:

```swift
.library(name: "SaveSystem", targets: ["SaveSystem"]),
```

Add these entries to `targets`:

```swift
.target(name: "SaveSystem", dependencies: ["AnnotationCore", "DatasetIO"]),
.testTarget(name: "SaveSystemTests", dependencies: ["AnnotationCore", "DatasetIO", "SaveSystem"]),
```

Create the source-directory marker that makes the still-incomplete target discoverable:

```swift
// macos/Sources/SaveSystem/FileFingerprint.swift
import Foundation
```

```swift
// macos/Tests/SaveSystemTests/SaveCoordinatorTests.swift
import XCTest
import AnnotationCore
@testable import SaveSystem

final class SaveCoordinatorTests: XCTestCase {
    func testSaveWritesAnnotationAndCatalog() async throws {
        let directory = try makeDirectory()
        let annotation = directory.appending(path: "a.txt")
        let classes = directory.appending(path: "classes.txt")
        let coordinator = SaveCoordinator(recoveryStore: recoveryStore())
        let result = try await coordinator.save(SaveRequest(
            files: [annotation: Data("0 0.5 0.5 0.2 0.2\n".utf8), classes: Data("car\n".utf8)],
            expectedFingerprints: [:], recoveryID: "dataset-a"
        ))
        guard case .saved(let fingerprints) = result else { return XCTFail("Expected saved") }
        XCTAssertEqual(try String(contentsOf: annotation, encoding: .utf8), "0 0.5 0.5 0.2 0.2\n")
        XCTAssertEqual(fingerprints.count, 2)
    }

    func testExternalChangeReturnsConflictWithoutOverwrite() async throws {
        let directory = try makeDirectory()
        let annotation = directory.appending(path: "a.txt")
        try Data("old\n".utf8).write(to: annotation)
        let original = try FileFingerprint.capture(url: annotation)
        try Data("external\n".utf8).write(to: annotation)
        let coordinator = SaveCoordinator(recoveryStore: recoveryStore())
        let result = try await coordinator.save(SaveRequest(
            files: [annotation: Data("local\n".utf8)],
            expectedFingerprints: [annotation: original], recoveryID: "dataset-a"
        ))
        XCTAssertEqual(result, .conflict([annotation]))
        XCTAssertEqual(try String(contentsOf: annotation, encoding: .utf8), "external\n")
    }

    private func makeDirectory() throws -> URL {
        let url = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func recoveryStore() -> RecoveryStore {
        RecoveryStore(directory: FileManager.default.temporaryDirectory.appending(path: UUID().uuidString))
    }
}
```

- [ ] **Step 2: Run focused tests and verify missing save types**

Run: `cd macos && swift test --filter SaveCoordinatorTests`

Expected: FAIL because `SaveCoordinator`, `SaveRequest`, `SaveOutcome`, and `RecoveryStore` do not exist.

- [ ] **Step 3: Implement SHA-256 fingerprints and Application Support recovery payloads**

```swift
// macos/Sources/SaveSystem/FileFingerprint.swift
import Foundation
import CryptoKit

public struct FileFingerprint: Codable, Equatable, Sendable {
    public let byteCount: Int
    public let sha256: String

    public static func capture(url: URL) throws -> FileFingerprint {
        let data = try Data(contentsOf: url)
        return FileFingerprint(
            byteCount: data.count,
            sha256: SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        )
    }
}
```

```swift
// macos/Sources/SaveSystem/RecoveryStore.swift
import Foundation

public struct RecoveryPayload: Codable, Equatable, Sendable {
    public let id: String
    public let files: [String: Data]
    public let createdAt: Date
}

public struct RecoveryStore: Sendable {
    public let directory: URL

    public init(directory: URL? = nil) {
        let resolved = directory ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appending(path: "SmartLabelImg/Recovery", directoryHint: .isDirectory)
        self.directory = resolved
    }

    public func write(id: String, files: [URL: Data]) throws {
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let payload = RecoveryPayload(
            id: id, files: Dictionary(uniqueKeysWithValues: files.map { ($0.key.path, $0.value) }),
            createdAt: Date()
        )
        try JSONEncoder().encode(payload).write(to: url(for: id), options: .atomic)
    }

    public func remove(id: String) throws {
        let target = url(for: id)
        if FileManager.default.fileExists(atPath: target.path) { try FileManager.default.removeItem(at: target) }
    }

    public func loadAll() throws -> [RecoveryPayload] {
        guard FileManager.default.fileExists(atPath: directory.path) else { return [] }
        return try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "json" }
            .map { try JSONDecoder().decode(RecoveryPayload.self, from: Data(contentsOf: $0)) }
            .sorted { $0.createdAt < $1.createdAt }
    }

    private func url(for id: String) -> URL {
        let safe = Data(id.utf8).base64EncodedString().replacingOccurrences(of: "/", with: "_")
        return directory.appending(path: safe).appendingPathExtension("json")
    }
}
```

- [ ] **Step 4: Implement the serialized save actor with preflight conflict detection and rollback**

```swift
// macos/Sources/SaveSystem/SaveCoordinator.swift
import Foundation

public struct SaveRequest: Sendable {
    public let files: [URL: Data]
    public let expectedFingerprints: [URL: FileFingerprint]
    public let recoveryID: String

    public init(files: [URL: Data], expectedFingerprints: [URL: FileFingerprint], recoveryID: String) {
        self.files = files
        self.expectedFingerprints = expectedFingerprints
        self.recoveryID = recoveryID
    }
}

public enum SaveOutcome: Equatable, Sendable {
    case saved([URL: FileFingerprint])
    case conflict([URL])
}

public actor SaveCoordinator {
    private let recoveryStore: RecoveryStore
    private let fileManager: FileManager

    public init(recoveryStore: RecoveryStore, fileManager: FileManager = .default) {
        self.recoveryStore = recoveryStore
        self.fileManager = fileManager
    }

    public func save(_ request: SaveRequest) throws -> SaveOutcome {
        try recoveryStore.write(id: request.recoveryID, files: request.files)
        let conflicts = try request.expectedFingerprints.compactMap { url, expected -> URL? in
            guard fileManager.fileExists(atPath: url.path) else { return url }
            return try FileFingerprint.capture(url: url) == expected ? nil : url
        }.sorted { $0.path < $1.path }
        guard conflicts.isEmpty else { return .conflict(conflicts) }

        let transaction = UUID().uuidString
        var staged: [URL: URL] = [:]
        var backups: [URL: URL] = [:]
        var committed: [URL] = []
        do {
            for (destination, data) in request.files {
                try fileManager.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
                let temporary = destination.deletingLastPathComponent()
                    .appending(path: ".smartlabelimg-\(transaction)-\(destination.lastPathComponent)")
                try data.write(to: temporary, options: [.atomic])
                staged[destination] = temporary
                if fileManager.fileExists(atPath: destination.path) {
                    let backup = destination.deletingLastPathComponent()
                        .appending(path: ".smartlabelimg-backup-\(transaction)-\(destination.lastPathComponent)")
                    try fileManager.copyItem(at: destination, to: backup)
                    backups[destination] = backup
                }
            }
            for destination in request.files.keys.sorted(by: { $0.path < $1.path }) {
                guard let temporary = staged[destination] else { continue }
                if fileManager.fileExists(atPath: destination.path) { try fileManager.removeItem(at: destination) }
                try fileManager.moveItem(at: temporary, to: destination)
                committed.append(destination)
            }
            for backup in backups.values { try? fileManager.removeItem(at: backup) }
            let fingerprints = try Dictionary(uniqueKeysWithValues: request.files.keys.map {
                ($0, try FileFingerprint.capture(url: $0))
            })
            try recoveryStore.remove(id: request.recoveryID)
            return .saved(fingerprints)
        } catch {
            for destination in committed where backups[destination] == nil {
                if fileManager.fileExists(atPath: destination.path) { try? fileManager.removeItem(at: destination) }
            }
            for (destination, backup) in backups {
                if fileManager.fileExists(atPath: destination.path) { try? fileManager.removeItem(at: destination) }
                if fileManager.fileExists(atPath: backup.path) { try? fileManager.moveItem(at: backup, to: destination) }
            }
            for temporary in staged.values where fileManager.fileExists(atPath: temporary.path) {
                try? fileManager.removeItem(at: temporary)
            }
            throw error
        }
    }
}
```

- [ ] **Step 5: Add and run a recovery-persistence test**

Add to `SaveCoordinatorTests.swift`:

```swift
func testConflictKeepsRecoveryPayload() async throws {
    let recovery = recoveryStore()
    let file = try makeDirectory().appending(path: "a.txt")
    try Data("disk\n".utf8).write(to: file)
    let result = try await SaveCoordinator(recoveryStore: recovery).save(SaveRequest(
        files: [file: Data("local\n".utf8)],
        expectedFingerprints: [file: FileFingerprint(byteCount: 0, sha256: "wrong")],
        recoveryID: "conflict"
    ))
    XCTAssertEqual(result, .conflict([file]))
    XCTAssertEqual(try recovery.loadAll().first?.files[file.path], Data("local\n".utf8))
}
```

Run: `cd macos && swift test --filter SaveCoordinatorTests && swift test`

Expected: PASS; conflicts do not overwrite disk, successful saves remove recovery, and conflicts retain recovery.

- [ ] **Step 6: Commit the safe save system**

```bash
git add macos/Sources/SaveSystem macos/Tests/SaveSystemTests
git commit -m "feat(macOS): add atomic save and recovery"
```

### Task 6: Minimal Native macOS Application Shell

**Files:**
- Modify: `macos/Package.swift`
- Create: `macos/Sources/SmartLabelImgApp/SmartLabelImgApp.swift`
- Create: `macos/Sources/SmartLabelImgApp/AppModel.swift`
- Create: `macos/Sources/SmartLabelImgApp/WelcomeView.swift`
- Create: `macos/Sources/SmartLabelImgApp/DatasetView.swift`
- Create: `macos/Resources/AppIcon-1024.png`
- Create: `macos/Resources/AppIcon.iconset/*`
- Create: `macos/Resources/AppIcon.icns`
- Create: `script/build_and_run.sh`
- Create: `.codex/environments/environment.toml`

**Interfaces:**
- Consumes: `DatasetSession`, `BookmarkStore`, `YOLOStore`, `VOCStore`, `SaveCoordinator`, and `AnnotationDocument`.
- Produces: A runnable SwiftUI executable with folder opening, YOLO/VOC selection, separate annotation folder selection, image navigation, object-count summary, save-state display, `Command-S`, a polished macOS icon, a staged `.app` bundle, and one verified build/run entrypoint.

- [ ] **Step 1: Add the executable target and a smoke-build entry point**

Add to `products` in `macos/Package.swift`:

```swift
.executable(name: "SmartLabelImg", targets: ["SmartLabelImgApp"]),
```

Add to `targets`:

```swift
.executableTarget(
    name: "SmartLabelImgApp",
    dependencies: ["AnnotationCore", "DatasetIO", "SaveSystem"]
),
```

```swift
// macos/Sources/SmartLabelImgApp/SmartLabelImgApp.swift
import SwiftUI

@main
struct SmartLabelImgApp: App {
    @StateObject private var model = AppModel()

    var body: some Scene {
        WindowGroup("Smart LabelImg") {
            Group {
                if model.session == nil { WelcomeView(model: model) }
                else { DatasetView(model: model) }
            }
            .frame(minWidth: 900, minHeight: 600)
        }
        .commands {
            CommandGroup(replacing: .saveItem) {
                Button("Save") { Task { await model.saveCurrent() } }
                    .keyboardShortcut("s", modifiers: .command)
                    .disabled(model.currentDocument == nil)
            }
        }
    }
}
```

- [ ] **Step 2: Build and verify the expected failure before `AppModel` exists**

Run: `cd macos && swift build --product SmartLabelImg`

Expected: FAIL with `cannot find 'AppModel' in scope`.

- [ ] **Step 3: Implement the main-actor app model and asynchronous dataset opening**

```swift
// macos/Sources/SmartLabelImgApp/AppModel.swift
import SwiftUI
import ImageIO
import AnnotationCore
import DatasetIO
import SaveSystem

enum AppSaveState: Equatable { case saved, saving, unsaved, conflict, failed(String) }

@MainActor
final class AppModel: ObservableObject {
    @Published var session: DatasetSession?
    @Published var currentIndex = 0
    @Published var currentDocument: AnnotationDocument?
    @Published var diagnostics: [AnnotationDiagnostic] = []
    @Published var format: AnnotationFormat = .yolo
    @Published var saveState: AppSaveState = .saved
    @Published var isChoosingImages = false
    @Published var isChoosingAnnotations = false
    @Published var classes: [String] = []

    private let bookmarkStore = BookmarkStore()
    private let saveCoordinator: SaveCoordinator
    private var fingerprints: [URL: FileFingerprint] = [:]

    init() {
        self.saveCoordinator = SaveCoordinator(recoveryStore: RecoveryStore())
    }

    func openImageDirectory(_ url: URL) {
        let selectedFormat = format
        Task {
            do {
                let discovered = try await Task.detached { try DatasetSession.discover(
                    imageDirectory: url, annotationDirectory: url, format: selectedFormat
                ) }.value
                try bookmarkStore.save(url: url, key: "imageDirectory")
                session = discovered
                currentIndex = 0
                await loadCurrent()
            } catch { saveState = .failed(error.localizedDescription) }
        }
    }

    func changeAnnotationDirectory(_ url: URL) {
        guard let old = session else { return }
        let selectedFormat = format
        Task {
            do {
                guard await saveCurrent() else { return }
                let discovered = try await Task.detached { try DatasetSession.discover(
                    imageDirectory: old.imageDirectory, annotationDirectory: url, format: selectedFormat
                ) }.value
                try bookmarkStore.save(url: url, key: "annotationDirectory")
                session = discovered
                await loadCurrent()
            } catch { saveState = .failed(error.localizedDescription) }
        }
    }

    func loadCurrent() async {
        guard let session, session.images.indices.contains(currentIndex) else { return }
        let imageURL = session.images[currentIndex]
        let annotationURL = session.annotationURL(for: imageURL)
        let classesURL = session.classesURL
        let readableClassesURL = session.readableClassesURL()
        let selectedFormat = session.format
        let classSnapshot = classes
        do {
            let loaded = try await Task.detached { () -> (AnnotationLoadResult, [URL: FileFingerprint], [String]) in
                let size = try Self.imageSize(url: imageURL)
                var resolvedClasses = classSnapshot
                if selectedFormat == .yolo, let readableClassesURL {
                    resolvedClasses = try ClassCatalog(data: Data(contentsOf: readableClassesURL), isLocked: true).names
                }
                var captured: [URL: FileFingerprint] = [:]
                if selectedFormat == .yolo, let readableClassesURL {
                    captured[readableClassesURL] = try FileFingerprint.capture(url: readableClassesURL)
                }
                guard FileManager.default.fileExists(atPath: annotationURL.path) else {
                    return (AnnotationLoadResult(
                        document: AnnotationDocument(imageURL: imageURL, imageSize: size), diagnostics: []
                    ), captured, resolvedClasses)
                }
                let data = try Data(contentsOf: annotationURL)
                captured[annotationURL] = try FileFingerprint.capture(url: annotationURL)
                let store: any AnnotationStore = selectedFormat == .yolo ? YOLOStore() : VOCStore()
                return (try store.load(
                    data: data, imageURL: imageURL, imageSize: size, classes: resolvedClasses
                ), captured, resolvedClasses)
            }.value
            currentDocument = loaded.0.document
            diagnostics = loaded.0.diagnostics
            fingerprints = loaded.1
            classes = loaded.2
            saveState = loaded.0.diagnostics.contains(where: { $0.severity == .blocking }) ? .conflict : .saved
        } catch { saveState = .failed(error.localizedDescription) }
    }

    @discardableResult
    func saveCurrent() async -> Bool {
        guard let session, let document = currentDocument else { return true }
        let annotationURL = session.annotationURL(for: document.imageURL)
        let classesURL = session.classesURL
        let selectedFormat = session.format
        let classSnapshot = classes
        do {
            saveState = .saving
            let files = try await Task.detached { () -> [URL: Data] in
                let store: any AnnotationStore = selectedFormat == .yolo ? YOLOStore() : VOCStore()
                var output = [annotationURL: try store.serialize(document: document, classes: classSnapshot)]
                if selectedFormat == .yolo {
                    output[classesURL] = classSnapshot.isEmpty
                        ? Data() : Data((classSnapshot.joined(separator: "\n") + "\n").utf8)
                }
                return output
            }.value
            let result = try await saveCoordinator.save(SaveRequest(
                files: files, expectedFingerprints: fingerprints,
                recoveryID: document.imageURL.standardizedFileURL.path
            ))
            switch result {
            case .saved(let updated): fingerprints = updated; saveState = .saved; return true
            case .conflict: saveState = .conflict; return false
            }
        } catch { saveState = .failed(error.localizedDescription); return false }
    }

    func selectImage(_ index: Int) {
        Task {
            guard await saveCurrent() else { return }
            currentIndex = index
            await loadCurrent()
        }
    }

    private nonisolated static func imageSize(url: URL) throws -> ImageSize {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any],
              let width = properties[kCGImagePropertyPixelWidth] as? Int,
              let height = properties[kCGImagePropertyPixelHeight] as? Int else {
            throw CocoaError(.fileReadCorruptFile)
        }
        return try ImageSize(width: width, height: height)
    }
}
```

- [ ] **Step 4: Implement the welcome and dataset views**

```swift
// macos/Sources/SmartLabelImgApp/WelcomeView.swift
import SwiftUI
import AppKit
import UniformTypeIdentifiers
import DatasetIO

struct WelcomeView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        VStack(spacing: 18) {
            Image(nsImage: NSApplication.shared.applicationIconImage).resizable().frame(width: 72, height: 72)
            Text("Smart LabelImg").font(.largeTitle.bold())
            Text("Create YOLO and Pascal VOC bounding-box datasets.").foregroundStyle(.secondary)
            Picker("Format", selection: $model.format) {
                Text("YOLO TXT").tag(AnnotationFormat.yolo)
                Text("Pascal VOC XML").tag(AnnotationFormat.pascalVOC)
            }.pickerStyle(.segmented).frame(width: 320)
            Button("Open Image Folder…") { model.isChoosingImages = true }.buttonStyle(.borderedProminent)
        }
        .fileImporter(
            isPresented: $model.isChoosingImages,
            allowedContentTypes: [.folder], allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first { model.openImageDirectory(url) }
        }
    }
}
```

```swift
// macos/Sources/SmartLabelImgApp/DatasetView.swift
import SwiftUI
import DatasetIO

struct DatasetView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationSplitView {
            List {
                ForEach(Array((model.session?.images ?? []).enumerated()), id: \.offset) { index, url in
                    Button(url.lastPathComponent) { model.selectImage(index) }
                        .buttonStyle(.plain)
                }
            }.navigationTitle("Images")
        } detail: {
            VStack(spacing: 16) {
                if let document = model.currentDocument {
                    Text(document.imageURL.lastPathComponent).font(.title2)
                    Text("\(document.imageSize.width) × \(document.imageSize.height)")
                    Text("\(document.boxes.count) boxes")
                    if !model.diagnostics.isEmpty {
                        Text("\(model.diagnostics.count) annotation problems").foregroundStyle(.red)
                    }
                }
                Spacer()
                Text(saveText).foregroundStyle(saveColor)
            }.padding()
        }
        .toolbar {
            Button("Annotation Folder…") { model.isChoosingAnnotations = true }
            Button("Save") { Task { await model.saveCurrent() } }
        }
        .fileImporter(
            isPresented: $model.isChoosingAnnotations,
            allowedContentTypes: [.folder], allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first { model.changeAnnotationDirectory(url) }
        }
    }

    private var saveText: String {
        switch model.saveState {
        case .saved: "Saved"
        case .saving: "Saving…"
        case .unsaved: "Unsaved"
        case .conflict: "File conflict"
        case .failed(let message): "Save failed: \(message)"
        }
    }

    private var saveColor: Color {
        switch model.saveState { case .saved: .secondary; case .saving, .unsaved: .orange; case .conflict, .failed: .red }
    }
}
```

- [ ] **Step 5: Generate and validate the professional application icon**

Use the `imagegen` skill with this exact art direction and save the selected square result as `macos/Resources/AppIcon-1024.png`:

```text
Create a polished macOS application icon for “Smart LabelImg”, a professional AI-assisted bounding-box annotation tool. A deep graphite-to-midnight-blue rounded-square object with generous macOS-style depth, a clean cyan annotation rectangle made from four precise corner brackets, and one restrained mint-green sparkle suggesting local AI refinement. No text, no letters, no Apple logo, no animals, no photo collage, no tiny details. Centered, balanced, friendly but technical, subtle soft highlights, excellent legibility at 16 px, premium first-party macOS aesthetic, full 1024×1024 square artwork.
```

Create the standard renditions and ICNS file:

```bash
mkdir -p macos/Resources/AppIcon.iconset
sips -z 16 16 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_16x16.png
sips -z 32 32 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_16x16@2x.png
sips -z 32 32 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_32x32.png
sips -z 64 64 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_32x32@2x.png
sips -z 128 128 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_128x128.png
sips -z 256 256 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_128x128@2x.png
sips -z 256 256 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_256x256.png
sips -z 512 512 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_256x256@2x.png
sips -z 512 512 macos/Resources/AppIcon-1024.png --out macos/Resources/AppIcon.iconset/icon_512x512.png
cp macos/Resources/AppIcon-1024.png macos/Resources/AppIcon.iconset/icon_512x512@2x.png
iconutil -c icns macos/Resources/AppIcon.iconset -o macos/Resources/AppIcon.icns
sips -g pixelWidth -g pixelHeight macos/Resources/AppIcon-1024.png
```

Expected: the source reports `pixelWidth: 1024` and `pixelHeight: 1024`; `iconutil` exits 0; the 16 px rendition still has a recognizable cyan bounding-box symbol and no text-like artifacts.

- [ ] **Step 6: Add the canonical SwiftPM GUI bundle build/run script and Codex Run action**

```bash
#!/usr/bin/env bash
# script/build_and_run.sh
set -euo pipefail

MODE="${1:-run}"
PRODUCT_NAME="SmartLabelImg"
DISPLAY_NAME="Smart LabelImg"
BUNDLE_ID="com.smartlabelimg.app"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/macos"
DIST_DIR="$ROOT_DIR/dist-native"
APP_BUNDLE="$DIST_DIR/$DISPLAY_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$PRODUCT_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"

pkill -x "$PRODUCT_NAME" >/dev/null 2>&1 || true
swift test --package-path "$PACKAGE_DIR"
swift build --package-path "$PACKAGE_DIR" --product "$PRODUCT_NAME"
BUILD_BINARY="$(swift build --package-path "$PACKAGE_DIR" --show-bin-path)/$PRODUCT_NAME"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp "$BUILD_BINARY" "$APP_BINARY"
cp "$PACKAGE_DIR/Resources/AppIcon.icns" "$APP_RESOURCES/AppIcon.icns"
chmod +x "$APP_BINARY"

plutil -create xml1 "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string $PRODUCT_NAME" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string $BUNDLE_ID" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleName string $DISPLAY_NAME" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string $DISPLAY_NAME" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundlePackageType string APPL" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string $MIN_SYSTEM_VERSION" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :NSPrincipalClass string NSApplication" "$INFO_PLIST"
plutil -lint "$INFO_PLIST"
codesign --force --deep --sign - "$APP_BUNDLE"
codesign --verify --deep --strict "$APP_BUNDLE"

open_app() { /usr/bin/open -n "$APP_BUNDLE"; }

case "$MODE" in
  run) open_app ;;
  --debug|debug) lldb -- "$APP_BINARY" ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$PRODUCT_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    sleep 2
    pgrep -x "$PRODUCT_NAME" >/dev/null
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify]" >&2
    exit 2
    ;;
esac
```

Make it executable with `chmod +x script/build_and_run.sh`.

```toml
# .codex/environments/environment.toml
# THIS IS AUTOGENERATED. DO NOT EDIT MANUALLY
version = 1
name = "smart-labelimg"

[setup]
script = ""

[[actions]]
name = "Run"
icon = "run"
command = "./script/build_and_run.sh"
```

- [ ] **Step 7: Build, test, stage, launch, and verify the application bundle**

Run: `./script/build_and_run.sh --verify`

Expected: all Swift tests pass, the executable builds, `Info.plist` validates, ad-hoc code-sign verification passes, the staged app launches, and `pgrep -x SmartLabelImg` succeeds.

Run: `./script/build_and_run.sh --logs`

Expected: A foreground app with the custom Dock icon opens. Selecting a folder lists images, selecting an image shows dimensions and box count, a separate annotation folder can be selected, Save reports Saved or an actionable error, and no uncaught-error or crash message appears in the app process log. Stop log streaming and quit the app after the smoke check.

- [ ] **Step 8: Commit the native app shell, icon, and verified run loop**

```bash
git add macos/Package.swift macos/Sources/SmartLabelImgApp macos/Resources script/build_and_run.sh .codex/environments/environment.toml
git commit -m "feat(macOS): add native dataset shell and app icon"
```

### Task 7: End-to-End Dataset Round Trip and Native Developer Documentation

**Files:**
- Modify: `macos/Package.swift`
- Create: `macos/Tests/IntegrationTests/DatasetRoundTripTests.swift`
- Create: `docs/native-development.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: All stage-one modules.
- Produces: A regression proving a real folder can round-trip YOLO and VOC through the safe save coordinator, plus exact native build/test/run instructions.

- [ ] **Step 1: Add the integration test target and write the failing round-trip test**

Add to `targets` in `macos/Package.swift`:

```swift
.testTarget(
    name: "IntegrationTests",
    dependencies: ["AnnotationCore", "DatasetIO", "SaveSystem"]
),
```

```swift
// macos/Tests/IntegrationTests/DatasetRoundTripTests.swift
import XCTest
import AnnotationCore
import DatasetIO
import SaveSystem

final class DatasetRoundTripTests: XCTestCase {
    func testYOLOAndVOCRoundTripThroughSaveCoordinator() async throws {
        let root = FileManager.default.temporaryDirectory.appending(path: UUID().uuidString)
        let images = root.appending(path: "images", directoryHint: .isDirectory)
        let labels = root.appending(path: "labels", directoryHint: .isDirectory)
        let recovery = root.appending(path: "recovery", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: images, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: labels, withIntermediateDirectories: true)
        let imageURL = images.appending(path: "frame.jpg")
        try Data().write(to: imageURL)
        let document = AnnotationDocument(
            imageURL: imageURL, imageSize: try ImageSize(width: 200, height: 100),
            boxes: [BoundingBox(className: "car", xMin: 80, yMin: 30, xMax: 120, yMax: 70)],
            isVerified: true
        )
        let coordinator = SaveCoordinator(recoveryStore: RecoveryStore(directory: recovery))

        let yoloURL = labels.appending(path: "frame.txt")
        _ = try await coordinator.save(SaveRequest(
            files: [yoloURL: try YOLOStore().serialize(document: document, classes: ["car"]),
                    labels.appending(path: "classes.txt"): Data("car\n".utf8)],
            expectedFingerprints: [:], recoveryID: "yolo"
        ))
        let loadedYOLO = try YOLOStore().load(
            data: Data(contentsOf: yoloURL), imageURL: imageURL,
            imageSize: document.imageSize, classes: ["car"]
        )
        XCTAssertEqual(loadedYOLO.document.boxes.map(\.className), ["car"])

        let vocURL = labels.appending(path: "frame.xml")
        _ = try await coordinator.save(SaveRequest(
            files: [vocURL: try VOCStore().serialize(document: document, classes: ["car"])],
            expectedFingerprints: [:], recoveryID: "voc"
        ))
        let loadedVOC = try VOCStore().load(
            data: Data(contentsOf: vocURL), imageURL: imageURL,
            imageSize: document.imageSize, classes: ["car"]
        )
        XCTAssertTrue(loadedVOC.document.isVerified)
        XCTAssertEqual(loadedVOC.document.boxes.map(\.className), ["car"])
    }
}
```

- [ ] **Step 2: Run the integration test and verify any wiring failure before documentation**

Run: `cd macos && swift test --filter DatasetRoundTripTests`

Expected: PASS; the saved YOLO file reloads with class `car`, and the saved VOC file reloads with class `car` and verified state enabled.

- [ ] **Step 3: Add exact native development documentation**

```markdown
<!-- docs/native-development.md -->
# Native macOS Development

The native rewrite lives in `macos/` and requires Apple Silicon, macOS 14 or later, and Swift 6.

## Test

```bash
cd macos
swift test
```

## Build

```bash
cd macos
swift build --product SmartLabelImg
```

## Run the stage-one app

```bash
./script/build_and_run.sh
```

Use `./script/build_and_run.sh --verify` to run tests, stage a signed local `.app`, launch it, and verify that the process remains alive. The existing Python app remains the feature-complete reference until later native stages add the annotation canvas and bundled SAM.
```

Add this section near the top of `README.md`, after the opening description:

```markdown
## Native macOS Rewrite

The Apple Silicon/macOS 14 native rewrite is being delivered in tested stages under `macos/`. See [`docs/native-development.md`](docs/native-development.md) for current build and test commands. The existing Python application remains available while native feature parity is in progress.
```

- [ ] **Step 4: Run final verification for the stage**

Run: `./script/build_and_run.sh --verify`

Expected: All tests PASS, the app bundle and icon stage successfully, signature validation passes, and the launched process remains alive.

Run: `git diff --check && git status --short`

Expected: No whitespace errors; only the intended integration test and documentation files are modified.

- [ ] **Step 5: Commit the verified native I/O milestone**

```bash
git add macos/Package.swift macos/Tests/IntegrationTests docs/native-development.md README.md
git commit -m "test(macOS): verify native dataset round trips"
```

## Stage-One Completion Gate

Before starting the professional canvas plan, verify all of the following:

- `cd macos && swift test` passes with no skipped tests.
- `cd macos && swift build --product SmartLabelImg` succeeds.
- `./script/build_and_run.sh --verify` builds, stages, signs, launches, and confirms the native app process.
- The Dock and About presentation use the custom Smart LabelImg icon, including a legible 16 px rendition.
- The smoke-run window opens a real image directory and a separate annotation directory.
- LabelImg-generated YOLO and VOC fixtures load without blocking diagnostics.
- YOLO save writes both the same-basename TXT file and `classes.txt`.
- An externally modified annotation returns Conflict and remains unchanged.
- A failed or conflicted save leaves a recovery payload outside the dataset directory.
- Duplicate image basenames are rejected before either annotation can be overwritten.
- Existing Python tests and files are untouched by the native milestone.
