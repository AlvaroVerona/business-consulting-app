import SwiftUI

struct SidebarView: View {
    @Environment(AppViewModel.self) private var appViewModel

    @State private var isPresentingNewCompany = false
    @State private var newCompanyForProject: Company?

    var body: some View {
        List {
            ForEach(appViewModel.companies) { company in
                Section {
                    ForEach(appViewModel.projectsByCompany[company.id] ?? []) { project in
                        Button {
                            appViewModel.selectedProject = project
                        } label: {
                            Label(project.name, systemImage: "briefcase")
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(appViewModel.selectedProject?.id == project.id ? Color.accentColor : .primary)
                    }

                    Button {
                        newCompanyForProject = company
                    } label: {
                        Label("New project…", systemImage: "plus.circle")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                } header: {
                    Label(company.name, systemImage: "building.2")
                }
            }
        }
        .navigationTitle("Companies")
        .toolbar {
            ToolbarItem {
                Button {
                    isPresentingNewCompany = true
                } label: {
                    Label("New company", systemImage: "plus")
                }
            }
        }
        .sheet(isPresented: $isPresentingNewCompany) {
            NewCompanySheet()
        }
        .sheet(item: $newCompanyForProject) { company in
            NewProjectSheet(company: company)
        }
    }
}

private struct NewCompanySheet: View {
    @Environment(AppViewModel.self) private var appViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var industry = ""

    var body: some View {
        Form {
            TextField("Company name", text: $name)
            TextField("Industry (optional)", text: $industry)
        }
        .padding()
        .frame(width: 320)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Cancel") { dismiss() }
            }
            ToolbarItem(placement: .confirmationAction) {
                Button("Create") {
                    Task {
                        await appViewModel.createCompany(
                            name: name,
                            industry: industry.isEmpty ? nil : industry
                        )
                        dismiss()
                    }
                }
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
    }
}

private struct NewProjectSheet: View {
    let company: Company

    @Environment(AppViewModel.self) private var appViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var description = ""

    var body: some View {
        Form {
            TextField("Project name", text: $name)
            TextField("Description (optional)", text: $description)
        }
        .padding()
        .frame(width: 320)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Cancel") { dismiss() }
            }
            ToolbarItem(placement: .confirmationAction) {
                Button("Create") {
                    Task {
                        await appViewModel.createProject(
                            companyId: company.id,
                            name: name,
                            description: description.isEmpty ? nil : description
                        )
                        dismiss()
                    }
                }
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
    }
}
