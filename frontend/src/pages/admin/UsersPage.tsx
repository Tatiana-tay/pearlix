import { useMemo, useState } from "react";
import { KeyRound, Plus, RotateCcw, Search, ShieldCheck, UserX } from "lucide-react";
import { PageHeader } from "../../components/layout/PageHeader";
import { DataTable, type DataColumn } from "../../components/tables/DataTable";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { FilterPopover } from "../../components/ui/FilterPopover";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { Select } from "../../components/ui/Select";
import type { Role, User, UserStatus } from "../../types/models";
import { prettyDate } from "../../utils/format";
import { loadMockUsers, saveMockUsers } from "../../utils/mockClinicState";
import { userStatusTone } from "../../utils/statusStyles";

const roles: Role[] = ["Admin", "Doctor", "Staff"];

export function UsersPage() {
  const [users, setUsers] = useState<User[]>(loadMockUsers);
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    fullName: "",
    username: "",
    email: "",
    phone: "",
    role: "Staff" as Role,
    status: "Active" as UserStatus,
    mustChangePassword: true,
  });

  const openModal = (user?: User) => {
    setSelectedUser(user ?? null);
    setForm(user ? {
      fullName: user.fullName,
      username: user.username,
      email: user.email,
      phone: user.phone,
      role: user.role,
      status: user.status,
      mustChangePassword: user.mustChangePassword,
    } : {
      fullName: "",
      username: "",
      email: "",
      phone: "",
      role: "Staff",
      status: "Active",
      mustChangePassword: true,
    });
    setModalOpen(true);
  };

  const persistUsers = (nextUsers: User[], nextMessage: string) => {
    setUsers(nextUsers);
    saveMockUsers(nextUsers);
    setMessage(nextMessage);
  };

  const saveUser = () => {
    if (!form.fullName.trim() || !form.username.trim() || !form.email.trim()) {
      setMessage("Full name, username, and email are required.");
      return;
    }

    const nextUser: User = {
      id: selectedUser?.id ?? `USR-${Date.now().toString().slice(-6)}`,
      fullName: form.fullName.trim(),
      username: form.username.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      role: form.role,
      status: form.status,
      createdAt: selectedUser?.createdAt ?? "2026-02-09",
      mustChangePassword: form.mustChangePassword,
    };
    const nextUsers = selectedUser
      ? users.map((user) => user.id === selectedUser.id ? nextUser : user)
      : [...users, nextUser];

    persistUsers(nextUsers, selectedUser ? "User updated." : "User added.");
    setModalOpen(false);
  };

  const updateUser = (userId: string, updates: Partial<User>, nextMessage: string) => {
    persistUsers(users.map((user) => user.id === userId ? { ...user, ...updates } : user), nextMessage);
  };

  const columns: DataColumn<User>[] = [
    { header: "Name", cell: (user) => <strong>{user.fullName}</strong> },
    { header: "Username", cell: (user) => user.username },
    { header: "Email", cell: (user) => user.email },
    { header: "Phone", cell: (user) => user.phone },
    { header: "Role", cell: (user) => <Badge tone="primary">{user.role}</Badge> },
    { header: "Status", cell: (user) => <Badge tone={userStatusTone[user.status]}>{user.status}</Badge> },
    { header: "Created At", cell: (user) => prettyDate(user.createdAt) },
  ];

  const filteredUsers = useMemo(() => {
    const normalized = query.toLowerCase();
    return users.filter((user) => {
      const text = `${user.fullName} ${user.username} ${user.email} ${user.phone}`.toLowerCase();
      const matchesRole = roleFilter === "All" || user.role === roleFilter;
      const matchesStatus = statusFilter === "All" || user.status === statusFilter;
      return text.includes(normalized) && matchesRole && matchesStatus;
    });
  }, [query, roleFilter, statusFilter, users]);

  const activeFilters = (roleFilter !== "All" ? 1 : 0) + (statusFilter !== "All" ? 1 : 0);

  return (
    <div className="page-shell">
      <PageHeader
        title="Users"
        subtitle="Create and manage clinic system users."
        actions={<Button icon={<Plus size={18} />} onClick={() => openModal()}>Add User</Button>}
      />
      {message && <div className={message.includes("required") ? "alert-card" : "notice-card"}>{message}</div>}
      <Card>
        <div className="filter-card">
          <Input icon={<Search size={18} />} placeholder="Search users by name, username, email, or phone..." value={query} onChange={(event) => setQuery(event.target.value)} />
          <FilterPopover activeCount={activeFilters}>
            <div className="filter-popover-content">
              <Select label="Role" options={["All", ...roles]} value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)} />
              <Select label="Status" options={["All", "Active", "Inactive"]} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
              <Button
                variant="ghost"
                type="button"
                onClick={() => {
                  setRoleFilter("All");
                  setStatusFilter("All");
                }}
              >
                Clear filters
              </Button>
            </div>
          </FilterPopover>
        </div>
      </Card>
      <Card>
        <DataTable columns={columns} rows={filteredUsers} getRowKey={(user) => user.id} onRowClick={openModal} />
      </Card>
      <Modal
        title={selectedUser ? "Edit User" : "Add User"}
        subtitle="Temporary access is local mock data only."
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        width={860}
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
            <Button onClick={saveUser}>Save User</Button>
          </>
        }
      >
        <div className="stack">
          <div className="field-grid">
            <Input label="Full name" required value={form.fullName} onChange={(event) => setForm((current) => ({ ...current, fullName: event.target.value }))} />
            <Input label="Username" required value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} />
            <Input label="Email" required type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} />
            <Input label="Phone" value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} />
            <Select label="Role" options={roles} value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as Role }))} />
            <Select label="Status" options={["Active", "Inactive"]} value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value as UserStatus }))} />
            <Input className="span-2" label="Temporary password / send setup email" value="Send setup email" readOnly />
          </div>
          <label className="checkbox-line">
            <input
              type="checkbox"
              checked={form.mustChangePassword}
              onChange={(event) => setForm((current) => ({ ...current, mustChangePassword: event.target.checked }))}
            />
            Must change password on next login
          </label>
          {selectedUser && (
            <div className="soft-panel">
              <h3 className="card-title">Admin actions</h3>
              <div className="right mt-16">
                <Button
                  variant="secondary"
                  icon={<ShieldCheck size={16} />}
                  onClick={() => setForm((current) => ({ ...current, role: current.role === "Staff" ? "Doctor" : "Staff" }))}
                >
                  Change role
                </Button>
                <Button
                  variant="secondary"
                  icon={<RotateCcw size={16} />}
                  onClick={() => selectedUser && updateUser(selectedUser.id, { mustChangePassword: true }, "Password reset instructions were mocked for this user.")}
                >
                  Send password reset
                </Button>
                <Button
                  variant="danger"
                  icon={<UserX size={16} />}
                  onClick={() => setForm((current) => ({ ...current, status: current.status === "Active" ? "Inactive" : "Active" }))}
                >
                  {form.status === "Active" ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </div>
          )}
          <div className="notice-card row"><KeyRound size={18} /> Password setup is mocked for the prototype.</div>
        </div>
      </Modal>
    </div>
  );
}
