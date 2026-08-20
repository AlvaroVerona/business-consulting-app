import Foundation

/// The JSON contract shared with the Python sidecar: snake_case <-> camelCase
/// key conversion, and a date format that has to handle both timezone-aware
/// ISO8601 and SQLite's naive (no-timezone) datetime strings. Extracted from
/// `SidecarClient` so this contract — which has already needed a second date
/// format added once — can be tested directly against fixture JSON, not only
/// indirectly through a live sidecar.
enum SidecarJSON {
    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let raw = try container.decode(String.self)

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = formatter.date(from: raw) { return date }

            // FastAPI/SQLite naive datetimes have no timezone suffix.
            let fallback = DateFormatter()
            fallback.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
            fallback.timeZone = TimeZone(identifier: "UTC")
            if let date = fallback.date(from: raw) { return date }

            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unrecognized date: \(raw)")
        }
        return decoder
    }()

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()
}
