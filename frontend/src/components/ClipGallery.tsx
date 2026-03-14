import type { Clip } from '../types';
import { ShareComposerModal } from './ShareComposerModal';
import { useClipGalleryController } from './clipGallery/useClipGalleryController';
import {
    DeleteClipModal,
    EmptyState,
    ErrorState,
    GalleryHeader,
    LoadingState,
    ReadyState,
} from './clipGallery/sections';

interface ClipGalleryProps {
    onEditClip?: (clip: Clip) => void;
    onAdvancedEditClip?: (clip: Clip) => void;
}

export const ClipGallery = ({ onAdvancedEditClip, onEditClip }: ClipGalleryProps) => {
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
                projectFilter={projectFilter}
                projectOptions={projectOptions}
                setProjectFilter={setProjectFilter}
                setSortOrder={setSortOrder}
                sortOrder={sortOrder}
                totalCount={totalCount}
                visibleCount={visibleCount}
            />
            {state === 'loading' && <LoadingState />}
            {state === 'error' && <ErrorState errorMsg={errorMsg} onRetry={handleRetry} />}
            {state === 'empty' && <EmptyState />}
            {state === 'ready' && (
                <ReadyState
                    clips={clips}
                    onAdvancedEditClip={onAdvancedEditClip}
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
