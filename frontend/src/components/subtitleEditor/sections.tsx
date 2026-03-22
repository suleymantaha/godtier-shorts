import { SelectionCard } from './selectionSection';
import {
  type SubtitleEditorContentProps,
  type TranscriptCardProps,
} from './sectionTypes';
import { SubtitleEditorPreviewStack } from './previewSection';
import { TranscriptCard } from './transcriptSection';
import type { SubtitleEditorController } from './useSubtitleEditorController';

export function SubtitleEditorLayout({ controller }: { controller: SubtitleEditorController }) {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <SubtitleEditorPanels controller={controller} />
    </div>
  );
}

function SubtitleEditorPanels({ controller }: { controller: SubtitleEditorController }) {
  return (
    <>
      {!controller.lockedToClip && (
        <SelectionCard
          clips={controller.clips}
          handleClipSelect={controller.handleClipSelect}
          mode={controller.mode}
          projects={controller.projects}
          projectsError={controller.projectsError}
          projectsStatus={controller.projectsStatus}
          sourceMessage={controller.sourceMessage}
          sourceState={controller.sourceState}
          resolveClipSelectValue={controller.resolveClipSelectValue}
          selectClipMode={controller.selectClipMode}
          selectProjectMode={controller.selectProjectMode}
          selectedClip={controller.selectedClip}
          selectedProjectId={controller.selectedProjectId}
          setSelectedProjectId={controller.setSelectedProjectId}
        />
      )}
      {controller.hasSelection && (
        <SubtitleEditorContent
          clipTranscriptCapabilities={controller.clipTranscriptCapabilities}
          clipTranscriptStatus={controller.clipTranscriptStatus}
          clipRenderMetadata={controller.clipRenderMetadata}
          currentJob={controller.currentJob}
          currentJobId={controller.currentJobId}
          currentTime={controller.currentTime}
          duration={controller.duration}
          endTime={controller.endTime}
          error={controller.error}
          handleLoadedMetadata={controller.handleLoadedMetadata}
          handleRangeChange={controller.handleRangeChange}
          handleRecoverProjectTranscript={controller.handleRecoverProjectTranscript}
          handleRecoverTranscript={controller.handleRecoverTranscript}
          handleRenderClip={controller.handleRenderClip}
          reloadTranscript={controller.reloadTranscript}
          handleSave={controller.handleSave}
          handleTimeUpdate={controller.handleTimeUpdate}
          isPlaying={controller.isPlaying}
          lockedToClip={controller.lockedToClip}
          loading={controller.loading}
          mode={controller.mode}
          projectTranscriptStatus={controller.projectTranscriptStatus}
          rangeReady={controller.rangeReady}
          reburnWarningMessage={controller.reburnWarningMessage}
          recommendedRecoveryStrategy={controller.recommendedRecoveryStrategy}
          saving={controller.saving}
          selectedClip={controller.selectedClip}
          selectedProjectId={controller.selectedProjectId}
          setAnimationType={controller.setAnimationType}
          setEndTime={controller.setEndTime}
          setIsPlaying={controller.setIsPlaying}
          setStartTime={controller.setStartTime}
          setStyle={controller.setStyle}
          animationType={controller.animationType}
          startTime={controller.startTime}
          style={controller.style}
          successMessage={controller.successMessage}
          togglePlay={controller.togglePlay}
          transcript={controller.transcript}
          transcriptAccessMessage={controller.transcriptAccessMessage}
          transcriptAccessState={controller.transcriptAccessState}
          updateSubtitleText={controller.updateSubtitleText}
          videoRef={controller.videoRef}
          videoSrc={controller.videoSrc}
          visibleTranscriptEntries={controller.visibleTranscriptEntries}
        />
      )}
    </>
  );
}

function SubtitleEditorContent(props: SubtitleEditorContentProps) {
  return (
    <>
      <SubtitleEditorPreviewStack {...buildPreviewStackProps(props)} />
      <SubtitleEditorTranscriptSection {...buildTranscriptSectionProps(props)} />
    </>
  );
}

function buildPreviewStackProps(props: SubtitleEditorContentProps) {
  return {
    clipRenderMetadata: props.clipRenderMetadata,
    currentJob: props.currentJob,
    currentJobId: props.currentJobId,
    duration: props.duration,
    endTime: props.endTime,
    handleLoadedMetadata: props.handleLoadedMetadata,
    handleRangeChange: props.handleRangeChange,
    handleTimeUpdate: props.handleTimeUpdate,
    isPlaying: props.isPlaying,
    mode: props.mode,
    rangeReady: props.rangeReady,
    selectedClip: props.selectedClip,
    setIsPlaying: props.setIsPlaying,
    startTime: props.startTime,
    togglePlay: props.togglePlay,
    transcriptCount: props.transcript.length,
    videoRef: props.videoRef,
    videoSrc: props.videoSrc,
    visibleCount: props.visibleTranscriptEntries.length,
  };
}

function buildTranscriptSectionProps(props: SubtitleEditorContentProps): TranscriptCardProps {
  return {
    animationType: props.animationType,
    clipTranscriptCapabilities: props.clipTranscriptCapabilities,
    clipTranscriptStatus: props.clipTranscriptStatus,
    currentJob: props.currentJob,
    currentTime: props.currentTime,
    endTime: props.endTime,
    error: props.error,
    handleRecoverProjectTranscript: props.handleRecoverProjectTranscript,
    handleRecoverTranscript: props.handleRecoverTranscript,
    handleRenderClip: props.handleRenderClip,
    reloadTranscript: props.reloadTranscript,
    handleSave: props.handleSave,
    loading: props.loading,
    lockedToClip: props.lockedToClip,
    mode: props.mode,
    projectTranscriptStatus: props.projectTranscriptStatus,
    reburnWarningMessage: props.reburnWarningMessage,
    recommendedRecoveryStrategy: props.recommendedRecoveryStrategy,
    saving: props.saving,
    selectedClip: props.selectedClip,
    selectedProjectId: props.selectedProjectId,
    setAnimationType: props.setAnimationType,
    setStyle: props.setStyle,
    startTime: props.startTime,
    style: props.style,
    successMessage: props.successMessage,
    transcript: props.transcript,
    transcriptAccessMessage: props.transcriptAccessMessage,
    transcriptAccessState: props.transcriptAccessState,
    updateSubtitleText: props.updateSubtitleText,
    videoRef: props.videoRef,
    visibleTranscriptEntries: props.visibleTranscriptEntries,
  };
}

function SubtitleEditorTranscriptSection(props: TranscriptCardProps) {
  return <TranscriptCard {...props} />;
}
