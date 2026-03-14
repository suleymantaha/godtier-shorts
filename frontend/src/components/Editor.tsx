import { EditorLayout } from './editor/sections';
import { type EditorProps, useEditorController } from './editor/useEditorController';

export const Editor = (props: EditorProps) => {
  const controller = useEditorController(props);

  return <EditorLayout controller={controller} />;
};
