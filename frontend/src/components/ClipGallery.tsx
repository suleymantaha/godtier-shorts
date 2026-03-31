import type { Clip } from '../types';
import { buildSocialComposeUrl } from './shareComposer/helpers';
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

function openSocialWorkspaceForClip(clip: Clip): void {
    if (typeof window === 'undefined') {
        return;
    }
    window.open(buildSocialComposeUrl(clip), '_self');
}

export const ClipGallery = ({ onEditClip }: ClipGalleryProps) => {
    const {
        authMode,
        clips,
        currentSubjectHash,
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
        setSortOrder,
        sortOrder,
        staleRefreshWarning,
        state,
        totalCount,
        visibleCount,
    } = useClipGalleryController();

    return (
        <div className="space-y-6">
            <GalleryHeader
                authMode={authMode}
                currentSubjectHash={currentSubjectHash}
                hasMore={hasMore}
                loadedCount={loadedCount}
                pageSizeLimit={pageSizeLimit}
                productionInProgress={productionInProgress}
                projectFilter={projectFilter}
                projectOptions={projectOptions}
                setProjectFilter={setProjectFilter}
                setSortOrder={setSortOrder}
                sortOrder={sortOrder}
                staleRefreshWarning={staleRefreshWarning}
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
                    onShareClip={openSocialWorkspaceForClip}
                />
            )}
            <DeleteClipModal
                clip={deleteClip}
                error={deleteError}
                isDeleting={isDeleting}
                onClose={handleCloseDelete}
                onConfirm={() => void handleConfirmDelete()}
            />
        </div>
    );
};
