import React from "react";
import {
  LayoutDashboard,
  Search,
  BookOpen,
  BrainCircuit,
  Stethoscope,
  FileText,
  Target,
  BarChart3,
  Calendar,
  CloudOff,
  CloudDownload,
  Maximize2,
  Minimize2,
  User,
  MoreHorizontal,
  Menu,
  X,
  Activity,
  HeartPulse,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  Scissors,
  Check,
  ChevronRight,
  ChevronLeft,
  ArrowRight,
  ArrowLeft,
  RotateCcw,
  Volume2,
  VolumeX,
  Play,
  Pause,
  Filter,
  Eye,
  EyeOff,
  Pencil,
  LucideIcon,
  LucideProps,
} from "lucide-react";

export const CLINICAL_ICON_MAP: Record<string, LucideIcon> = {
  // Navigation
  dashboard: LayoutDashboard,
  search: Search,
  menu_book: BookOpen,
  psychology: BrainCircuit,
  stethoscope: Stethoscope,
  description: FileText,
  my_location: Target,
  analytics: BarChart3,
  calendar_month: Calendar,
  
  // Status & System
  local_hospital: Activity,
  cloud_off: CloudOff,
  cloud_download: CloudDownload,
  fullscreen: Maximize2,
  fullscreen_exit: Minimize2,
  person: User,
  more_horiz: MoreHorizontal,
  menu: Menu,
  close: X,
  
  // Clinical Semiotics
  vital_signs: HeartPulse,
  heart: HeartPulse,
  warning: AlertTriangle,
  check: Check,
  check_circle: CheckCircle2,
  cancel: XCircle,
  schedule: Clock,
  sparkles: Sparkles,
  scissors: Scissors,
  chevron_right: ChevronRight,
  chevron_left: ChevronLeft,
  arrow_forward: ArrowRight,
  arrow_back: ArrowLeft,
  refresh: RotateCcw,
  volume_up: Volume2,
  volume_off: VolumeX,
  play_arrow: Play,
  pause: Pause,
  filter_list: Filter,
  visibility: Eye,
  visibility_off: EyeOff,
  edit: Pencil,
};

export interface ClinicalIconProps extends Omit<LucideProps, "ref"> {
  name: string;
  className?: string;
  strokeWidth?: number;
}

export function ClinicalIcon({
  name,
  className = "w-4 h-4",
  strokeWidth = 1.85,
  ...props
}: ClinicalIconProps) {
  const IconComponent = CLINICAL_ICON_MAP[name] || Activity;
  return <IconComponent className={className} strokeWidth={strokeWidth} aria-hidden="true" {...props} />;
}
