import { AlertCircle, Subtitles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { Select } from '../ui/Select';
import type { SelectionCardProps } from './sectionTypes';
import type { SubtitleEditorController } from './useSubtitleEditorController';

function ModeButtons({
  mode,
  selectClipMode,
  selectProjectMode,
}: Pick<SubtitleEditorController, 'mode' | 'selectClipMode' | 'selectProjectMode'>) {
  const { t } = useTranslation();

  return (
    <div className="flex-1 space-y-2">
      <label className="text-[11px] text-muted-foreground uppercase block">{t('subtitleEditor.selection.mode')}</label>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={selectProjectMode}
          className={`px-4 py-2 rounded-lg text-[11px] font-mono uppercase border transition-all ${mode === 'project' ? 'bg-accent/20 border-accent/40 text-foreground' : 'bg-foreground/5 border-border text-muted-foreground'}`}
        >
          {t('subtitleEditor.selection.project')}
        </button>
        <button
          type="button"
          onClick={selectClipMode}
          className={`px-4 py-2 rounded-lg text-[11px] font-mono uppercase border transition-all ${mode === 'clip' ? 'bg-accent/20 border-accent/40 text-foreground' : 'bg-foreground/5 border-border text-muted-foreground'}`}
        >
          {t('subtitleEditor.selection.clip')}
        </button>
      </div>
    </div>
  );
}

function SourceSelector({
  clips,
  handleClipSelect,
  mode,
  projects,
  resolveClipSelectValue,
  selectedClip,
  selectedProjectId,
  setSelectedProjectId,
}: Pick<
  SubtitleEditorController,
  | 'clips'
  | 'handleClipSelect'
  | 'mode'
  | 'projects'
  | 'resolveClipSelectValue'
  | 'selectedClip'
  | 'selectedProjectId'
  | 'setSelectedProjectId'
>) {
  const { t } = useTranslation();

  return (
    <div className="flex-1 space-y-2">
      <label className="text-[11px] text-muted-foreground uppercase block">
        {mode === 'project' ? t('subtitleEditor.selection.project') : t('subtitleEditor.selection.clip')}
      </label>
      {mode === 'project' ? (
        <Select
          value={selectedProjectId ?? ''}
          onChange={(value) => setSelectedProjectId(value || null)}
          options={[
            { label: t('subtitleEditor.selection.selectProject'), value: '' },
            ...projects.map((project) => ({ label: project.id, value: project.id })),
          ]}
          className="text-xs"
        />
      ) : (
        <Select
          value={resolveClipSelectValue(selectedClip)}
          onChange={handleClipSelect}
          options={[
            { label: t('subtitleEditor.selection.selectClip'), value: '' },
            ...clips.map((clip) => ({
              label: clip.name,
              value: `${clip.project ?? 'legacy'}:${clip.name}`,
            })),
          ]}
          className="text-xs"
        />
      )}
    </div>
  );
}

export function SelectionCard({
  clips,
  handleClipSelect,
  mode,
  projects,
  projectsError,
  projectsStatus,
  sourceMessage,
  sourceState,
  resolveClipSelectValue,
  selectClipMode,
  selectProjectMode,
  selectedClip,
  selectedProjectId,
  setSelectedProjectId,
}: SelectionCardProps) {
  const { t } = useTranslation();

  return (
    <div className="glass-card p-5 border-accent/20">
      <h2 className="text-xs font-mono uppercase tracking-[0.2em] text-accent flex items-center gap-2 mb-4">
        <Subtitles className="w-4 h-4" />
        {t('subtitleEditor.selection.title')}
      </h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <ModeButtons mode={mode} selectClipMode={selectClipMode} selectProjectMode={selectProjectMode} />
        <SourceSelector
          clips={clips}
          handleClipSelect={handleClipSelect}
          mode={mode}
          projects={projects}
          resolveClipSelectValue={resolveClipSelectValue}
          selectedClip={selectedClip}
          selectedProjectId={selectedProjectId}
          setSelectedProjectId={setSelectedProjectId}
        />
      </div>
      {projectsError && mode === 'project' && (
        <p
          className={`text-[11px] mt-2 flex items-center gap-1.5 ${projectsStatus === 'degraded' ? 'text-amber-300/90' : 'text-red-400/90'}`}
        >
          <AlertCircle className="w-3 h-3 shrink-0" />
          {projectsStatus === 'degraded'
            ? t('subtitleEditor.selection.degradedProjects', { message: projectsError })
            : projectsError}
        </p>
      )}
      {sourceState === 'auth_blocked' && (
        <p className="text-[11px] mt-2 flex items-center gap-1.5 text-amber-300/90">
          <AlertCircle className="w-3 h-3 shrink-0" />
          {sourceMessage}
        </p>
      )}
      {sourceState === 'loading' && projects.length === 0 && clips.length === 0 && (
        <p className="text-[11px] text-muted-foreground mt-2">{t('subtitleEditor.selection.loadingSources')}</p>
      )}
      {sourceState === 'ready' && projects.length === 0 && mode === 'project' && projectsStatus === 'good' && !projectsError && (
        <p className="text-[11px] text-muted-foreground mt-2">{t('subtitleEditor.selection.noProjects')}</p>
      )}
      {sourceState === 'ready' && clips.length === 0 && mode === 'clip' && (
        <p className="text-[11px] text-muted-foreground mt-2">{t('subtitleEditor.selection.noClips')}</p>
      )}
    </div>
  );
}
