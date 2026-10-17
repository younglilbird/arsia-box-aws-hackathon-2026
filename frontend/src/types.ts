export interface BoxFile {
  id?: string; name: string; url?: string; size?: number; extension?: string;
  document_category?: string; format?: string;
  origin_url?: string;
  material_id?: string;
}
export interface BoxBrowseEntry extends BoxFile { id: string; type: 'file' | 'folder'; version_id?: string; }
export interface BoxBrowseFolder { id: string; name: string; parent?: { id: string; name: string } | null; entries: BoxBrowseEntry[]; truncated?: boolean; }
export interface Category { name: string; files: BoxFile[]; filecount?: number; url?: string; }
export interface AppStatus {
  box: { connected: boolean; identity?: { name?: string; id?: string }; profile?: { name?: string }; mode?: string; error?: string };
  aws?: { configured?: boolean; region?: string; model_id?: string };
  categories: Category[]; employee_name: string; year: number;
  reports?: BoxFile[]; reports_folder_url?: string; workspace_folder_url?: string;
  cloudlatest?: unknown;
}
export interface Evidence {
  id: string; source_id?: string; source_name?: string; source_url?: string; url?: string;
  quote: string; claim?: string; project?: string; category?: string; document_category?: string;
  status?: string; attribution?: string;
}
export interface Issue { severity?: string; message: string; evidence_ids?: string[]; suggestion?: string; }
export interface EvaluationDimension {
  id: string; name: string; weight?: number; score?: number; rationale?: string;
  strengths?: string[]; improvements?: string[]; evidence_ids?: string[];
}
export interface Evaluation {
  status?: string; report_hash?: string; evaluated_at?: string; overall_score?: number;
  dimensions?: EvaluationDimension[]; summary?: string; strengths?: string[]; improvements?: string[];
  leadership_alignment?: Array<{ principle: string; explanation: string; evidence_ids?: string[] }>;
  issues?: Issue[]; missing_information?: string[];
}
export interface Evaluations {
  rubric_version?: string; score_label?: string; initial?: Evaluation; final?: Evaluation; overall_delta?: number | null;
}
export interface Coverage {
  discovered_files?: number; discovered?: number; selected_files?: number; read_files?: number;
  analyzed_files?: number; evidence_count?: number; character_coverage?: number;
  truncated?: boolean; warnings?: string[];
  skipped?: Array<{ id?: string; name?: string; reason: string }>;
}
export interface Run {
  id: string; status: 'queued' | 'running' | 'processing' | 'completed' | 'failed' | string;
  employee_name?: string; year?: number; stage?: string; progress?: number;
  created_at?: string | number; updated_at?: string | number;
  events?: Array<{ at?: string | number; stage?: string; message?: string }>;
  sources?: BoxFile[]; evidence?: Evidence[]; report_markdown?: string; initial_draft?: string;
  review?: { issues?: Issue[]; unresolved_issues?: Issue[]; revision_performed?: boolean; checks?: Record<string, unknown>;
    box_ai?: { status?: string; answer?: string; message?: string; citations?: unknown[]; file_ids?: string[]; file_count?: number; draft_truncated?: boolean; note?: string } };
  coverage?: Coverage; missing_information?: string[]; reviewer_confirmed?: boolean;
  box_files?: BoxFile[]; draft_box_files?: BoxFile[]; error?: string | { message?: string };
  addendum_file?: BoxFile; notes?: string;
  save_warnings?: string[]; user_edited?: boolean; saved_file_history?: BoxFile[];
  evaluations?: Evaluations;
  improvement_error?: string | null;
  improvement?: { round?: number; status?: string; target_score?: number; report_changed?: boolean };
  deletion_preview?: { tracked_output_count?: number; can_delete?: boolean };
}
export interface DeleteResult { id: string; deleted: boolean; status: string; removed_count?: number; already_absent_count?: number; shared_preserved_count?: number; remaining_count?: number; warnings?: string[]; run?: Run; }
export interface MaterialDeleteResult { deleted: boolean; status: 'deleted' | 'unavailable' | 'failed'; warnings?: string[]; }
