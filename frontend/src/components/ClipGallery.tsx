import type { Clip } from '../types';
import { openSocialComposeWindow } from './shareComposer/helpers';
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
        authMode,
        clips,
        currentSubjectHash,
        deleteClip,
        deleteError,
        handleCloseDelete,
        handleClaimProject,
        handleConfirmDelete,
        handleRequestDelete,
        errorMsg,
        handleRetry,
        hasMore,
        isClaimingProjectId,
        isDeleting,
        loadedCount,
        ownershipNotice,
        ownershipNoticeTone,
        pageSizeLimit,
        productionInProgress,
        projectFilter,
        projectOptions,
        reclaimableProjects,
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
                handleClaimProject={handleClaimProject}
                isClaimingProjectId={isClaimingProjectId}
                loadedCount={loadedCount}
                ownershipNotice={ownershipNotice}
                ownershipNoticeTone={ownershipNoticeTone}
                pageSizeLimit={pageSizeLimit}
                productionInProgress={productionInProgress}
                projectFilter={projectFilter}
                projectOptions={projectOptions}
                reclaimableProjects={reclaimableProjects}
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
                    onShareClip={openSocialComposeWindow}
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
