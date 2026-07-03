import type { DoctorProfile, DoctorWorkingHour, StaffShift } from "../types/models";

export const mockDoctors: DoctorProfile[] = [
  {
    Doctor_ID: "DOC-001",
    User_ID: "USR-002",
    Full_Name: "Dr. Sarah Wilson",
    role: "Doctor",
    Specialty: "General Dentistry",
    gender: "Female",
    Phone: "(555) 111-2222",
    Email: "sarah.wilson@dentalcare.local",
    Status: "Active",
  },
  {
    Doctor_ID: "DOC-002",
    User_ID: "USR-004",
    Full_Name: "Dr. Michael Martinez",
    role: "Doctor",
    Specialty: "Endodontics",
    gender: "Male",
    Phone: "(555) 222-3333",
    Email: "michael.martinez@dentalcare.local",
    Status: "Active",
  },
  {
    Doctor_ID: "DOC-003",
    User_ID: "USR-007",
    Full_Name: "Dr. Emily Chen",
    role: "Doctor",
    Specialty: "Orthodontics",
    gender: "Female",
    Phone: "(555) 333-4444",
    Email: "emily.chen@dentalcare.local",
    Status: "On Leave",
  },
  {
    Doctor_ID: "DOC-004",
    User_ID: "USR-005",
    Full_Name: "Jessica Brown",
    role: "Staff",
    Specialty: "Dental Hygienist",
    gender: "Female",
    Phone: "(555) 444-5555",
    Email: "jessica.brown@dentalcare.local",
    Status: "Active",
  },
  {
    Doctor_ID: "STF-001",
    User_ID: "USR-003",
    Full_Name: "Olivia Bennett",
    role: "Staff",
    Specialty: "Reception / Front Desk",
    gender: "Female",
    Phone: "(555) 103-4400",
    Email: "olivia.bennett@dentalcare.local",
    Status: "Active",
  },
  {
    Doctor_ID: "STF-002",
    User_ID: "USR-006",
    Full_Name: "Noah Price",
    role: "Staff",
    Specialty: "Billing Coordinator",
    gender: "Male",
    Phone: "(555) 310-1188",
    Email: "noah.price@dentalcare.local",
    Status: "Inactive",
  },
];

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const mockStaffShifts: StaffShift[] = mockDoctors.flatMap((doctor, doctorIndex) =>
  days.flatMap((day, index) => {
    const weekend = day === "Saturday" || day === "Sunday";
    const thursdayLeave = doctor.Doctor_ID === "DOC-002" && day === "Thursday";
    const emilyLeave = doctor.Doctor_ID === "DOC-003" && ["Monday", "Tuesday", "Wednesday"].includes(day);
    const staffProfile = doctor.Doctor_ID.startsWith("STF-");
    const isLeave = weekend || thursdayLeave || emilyLeave;

    const baseShift = {
      userId: doctor.User_ID,
      staffOrDoctorId: doctor.Doctor_ID,
      dayOfWeek: day,
      isOnLeave: isLeave,
    };

    const morningShift = {
      ...baseShift,
      id: `SHIFT-${doctorIndex + 1}-${index + 1}-1`,
      shiftName: "Morning",
      shiftIndex: 1,
      startTime: isLeave ? "-" : staffProfile ? "08:30" : doctor.Doctor_ID === "DOC-002" ? "10:00" : "09:00",
      endTime: isLeave ? "-" : staffProfile ? "13:00" : day === "Friday" ? "14:00" : "13:00",
    };

    if (isLeave || day === "Friday") {
      return [morningShift];
    }

    return [
      morningShift,
      {
        ...baseShift,
        id: `SHIFT-${doctorIndex + 1}-${index + 1}-2`,
        shiftName: "Evening",
        shiftIndex: 2,
        startTime: staffProfile ? "14:00" : "16:00",
        endTime: staffProfile ? "17:00" : doctor.Doctor_ID === "DOC-002" ? "20:00" : "18:00",
      },
    ];
  }),
);

const shiftToWorkingHour = (shift: StaffShift, doctorId: string): DoctorWorkingHour => ({
  Working_Hour_ID: shift.id,
  Doctor_ID: doctorId,
  Day_Of_Week: shift.dayOfWeek,
  Start_Time: shift.startTime,
  End_Time: shift.endTime,
  Is_On_Leave: shift.isOnLeave,
});

export const getShiftsForUser = (userId: string) =>
  mockStaffShifts.filter((shift) => shift.userId === userId);

export const getShiftsForProfile = (profileId: string) => {
  const profile = mockDoctors.find((doctor) => doctor.Doctor_ID === profileId);
  return profile ? getShiftsForUser(profile.User_ID) : [];
};

export const mockWorkingHours: DoctorWorkingHour[] = mockDoctors.flatMap((doctor) =>
  getShiftsForUser(doctor.User_ID).map((shift) => shiftToWorkingHour(shift, doctor.Doctor_ID)),
);

export const getWorkingHoursForProfile = (profileId: string) => {
  const profile = mockDoctors.find((doctor) => doctor.Doctor_ID === profileId);
  return profile ? getShiftsForUser(profile.User_ID).map((shift) => shiftToWorkingHour(shift, profile.Doctor_ID)) : [];
};

export const getWorkingHoursForUser = (userId: string) => {
  const profile = mockDoctors.find((doctor) => doctor.User_ID === userId);
  return profile ? getWorkingHoursForProfile(profile.Doctor_ID) : [];
};

export const getProfileForUser = (userId: string) =>
  mockDoctors.find((doctor) => doctor.User_ID === userId);

export const isDoctorProfile = (profile: DoctorProfile) => profile.role === "Doctor";
