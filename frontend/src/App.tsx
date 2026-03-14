import { AppBackground, SignedInShell, SignedOutScreen } from './app/sections';
import { useAppShellController } from './app/useAppShellController';

function App() {
  const controller = useAppShellController();

  return (
    <>
      <AppBackground />
      <div className="min-h-screen bg-transparent px-4 py-4 md:px-8 md:py-6 lg:px-12 lg:py-8 space-y-8 mx-auto w-full">
        <SignedOutScreen />
        <SignedInShell {...controller} />
      </div>
    </>
  );
}

export default App;
