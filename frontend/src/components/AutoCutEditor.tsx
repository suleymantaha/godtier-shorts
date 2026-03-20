import React from 'react';

import { AutoCutEditorLayout } from './autoCutEditor/sections';
import { useAutoCutEditorController } from './autoCutEditor/useAutoCutEditorController';

interface AutoCutEditorProps {
  onOpenLibrary?: () => void;
}

export const AutoCutEditor: React.FC<AutoCutEditorProps> = ({ onOpenLibrary }) => {
  const controller = useAutoCutEditorController({ onOpenLibrary });

  return <AutoCutEditorLayout controller={controller} />;
};
