import type { Clip } from '../types';
import { ShareComposerModal } from './ShareComposerModal';
import { useClipGalleryController } from './clipGallery/useClipGalleryController';
import {
    AuthBlockedState,
    DeleteClipModal,
    EmptyState,
    ErrorState,
    GalleryHeader,
    LoadingState,
    ProcessingState,
    ReadyState,
} from './clipGallery/sections';

interface ClipGalleryProps {
    onEditClip?: (clip: Clip) => void;
}

export const ClipGallery = ({ onEditClip }: ClipGalleryProps) => {
    const {
        clips,
        deleteClip,
        deleteError,
        handleCloseDelete,
        handleConfirmDelete,
        handleRequestDelete,
        errorMsg,
        handleRetry,
        hasMore,
        isDeleting,
        loadedCount,
        pageSizeLimit,
        productionInProgress,
        projectFilter,
        projectOptions,
        setProjectFilter,
        setShareClip,
        setSortOrder,
        shareClip,
        sortOrder,
        state,
        totalCount,
        visibleCount,
    } = useClipGalleryController();

    return (
        <div className="space-y-6">
            <GalleryHeader
                hasMore={hasMore}
                loadedCount={loadedCount}
                pageSizeLimit={pageSizeLimit}
                productionInProgress={productionInProgress}
                projectFilter={projectFilter}
                projectOptions={projectOptions}
                setProjectFilter={setProjectFilter}
                setSortOrder={setSortOrder}
                sortOrder={sortOrder}
                totalCount={totalCount}
                visibleCount={visibleCount}
            />
            {state === 'loading' && <LoadingState />}
            {state === 'processing' && <ProcessingState />}
            {state === 'auth_blocked' && <AuthBlockedState errorMsg={errorMsg} onRetry={handleRetry} />}
            {state === 'error' && <ErrorState errorMsg={errorMsg} onRetry={handleRetry} />}
            {state === 'empty' && <EmptyState />}
            {state === 'ready' && (
                <ReadyState
                    clips={clips}
                    onDeleteClip={handleRequestDelete}
                    onEditClip={onEditClip}
                    onShareClip={setShareClip}
                />
            )}
            <DeleteClipModal
                clip={deleteClip}
                error={deleteError}
                isDeleting={isDeleting}
                onClose={handleCloseDelete}
                onConfirm={() => void handleConfirmDelete()}
            />
            <ShareComposerModal open={Boolean(shareClip)} clip={shareClip} onClose={() => setShareClip(null)} />
        </div>
    );
};
