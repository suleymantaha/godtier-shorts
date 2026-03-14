import React from 'react';

import { AutoCutEditorLayout } from './autoCutEditor/sections';
import { useAutoCutEditorController } from './autoCutEditor/useAutoCutEditorController';

export const AutoCutEditor: React.FC = () => {
  const controller = useAutoCutEditorController();

  return <AutoCutEditorLayout controller={controller} />;
};
