import AppKit
import SwiftUI

/// macOS's native `.alert()` renders its message via NSAlert, whose text is
/// not selectable — there is no modifier that changes that, `.textSelection`
/// included, since the text isn't drawn by SwiftUI at all. Found live: an
/// error message (a raw sidecar failure detail, useful for diagnosing but
/// not memorizable) couldn't be copied out of the alert at all. This sheet
/// replaces `.alert()` for error display specifically so the message is
/// both selectable and one-click-copyable.
private struct CopyableErrorSheet: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Label("Something went wrong", systemImage: "exclamationmark.triangle.fill")
                .font(.headline)
                .foregroundStyle(.orange)

            ScrollView {
                Text(message)
                    .textSelection(.enabled)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 240)

            HStack {
                Button {
                    let pasteboard = NSPasteboard.general
                    pasteboard.clearContents()
                    pasteboard.setString(message, forType: .string)
                } label: {
                    Label("Copy", systemImage: "doc.on.doc")
                }

                Spacer()

                Button("OK", role: .cancel, action: onDismiss)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(minWidth: 420, idealWidth: 480)
    }
}

extension View {
    /// Drop-in replacement for `.alert(isPresented:message:)` for error text
    /// specifically — see `CopyableErrorSheet`'s doc comment for why.
    func copyableErrorSheet(message: Binding<String?>) -> some View {
        sheet(isPresented: Binding(get: { message.wrappedValue != nil }, set: { if !$0 { message.wrappedValue = nil } })) {
            CopyableErrorSheet(message: message.wrappedValue ?? "") {
                message.wrappedValue = nil
            }
        }
    }
}
