import {
  JobFormAutoPilotSection,
  JobFormControlGridSection,
  JobFormErrorAlert,
  JobFormSourceSection,
  JobFormSubmitButton,
} from './jobForm/sections';
import { type JobFormProps, useJobFormController } from './jobForm/useJobFormController';

export const JobForm = (props: JobFormProps = {}) => {
  const controller = useJobFormController(props);

  return (
    <form onSubmit={controller.handleStart} className="space-y-5">
      <JobFormSourceSection
        isSubmitting={controller.isSubmitting}
        onResolutionChange={controller.setResolution}
        onUrlChange={controller.setUrl}
        resolution={controller.resolution}
        resolutionId={controller.resolutionId}
        url={controller.url}
        urlId={controller.urlId}
      />
      <JobFormControlGridSection
        animationId={controller.animationId}
        animationType={controller.animationType}
        engine={controller.engine}
        engineId={controller.engineId}
        isSubmitting={controller.isSubmitting}
        layout={controller.layout}
        layoutId={controller.layoutId}
        numClips={controller.numClips}
        numClipsId={controller.numClipsId}
        onAnimationChange={controller.setAnimationType}
        onEngineChange={controller.setEngine}
        onLayoutChange={controller.setLayout}
        onNumClipsChange={controller.setNumClips}
        onSkipSubtitlesChange={controller.setSkipSubtitles}
        onStyleChange={controller.setStyle}
        skipSubtitles={controller.skipSubtitles}
        style={controller.style}
        styleId={controller.styleId}
      />
      <JobFormAutoPilotSection
        autoMode={controller.autoMode}
        durationMax={controller.durationMax}
        durationMaxId={controller.durationMaxId}
        durationMin={controller.durationMin}
        durationMinId={controller.durationMinId}
        isSubmitting={controller.isSubmitting}
        onAutoModeChange={controller.setAutoMode}
        onDurationMaxChange={controller.setDurationMax}
        onDurationMinChange={controller.setDurationMin}
      />
      <JobFormErrorAlert error={controller.error} />
      <JobFormSubmitButton disabled={controller.isSubmitting || !controller.url} isSubmitting={controller.isSubmitting} />
    </form>
  );
};
