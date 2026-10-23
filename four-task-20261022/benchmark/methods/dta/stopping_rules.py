"""Read-only validation of the predeclared full-observation early-stopping rule."""
def validate_stopping(epochs,best_epoch,train_n,max_epochs=20,patience=5):
    if not 1<=len(epochs)<=max_epochs:
        raise ValueError('Invalid epoch count')
    if [e['epoch'] for e in epochs]!=list(range(len(epochs))):
        raise ValueError('Epoch log is not complete and consecutive')
    if any(e['train_n']!=train_n for e in epochs):
        raise ValueError('Epoch omitted or duplicated training observations')
    chosen=min(range(len(epochs)),key=lambda i:epochs[i]['validation']['MAE'])
    if chosen!=best_epoch:
        raise ValueError('Best epoch does not follow strict validation selection')
    stale=len(epochs)-1-best_epoch
    if stale>patience:
        raise ValueError('Training exceeded the predeclared patience stop')
    if len(epochs)<max_epochs and stale<patience:
        raise ValueError('Prematurely truncated candidate, neither patience nor epoch bound reached')
    running_best=float('inf');running_stale=0
    for i,e in enumerate(epochs):
        improved=e['validation']['MAE']<running_best
        if e['improved']!=improved:
            raise ValueError('Improvement flag disagrees with strict MAE rule')
        if improved:running_best=e['validation']['MAE'];running_stale=0
        else:running_stale+=1
        if running_stale>=patience and i!=len(epochs)-1:
            raise ValueError('Candidate continued after an earlier patience stop')
    return {'epochs':len(epochs),'best_epoch':best_epoch,'stale_at_stop':stale,
            'patience_exhausted':stale>=patience,
            'epoch_bound_reached':len(epochs)==max_epochs,
            'epoch_bound_without_patience':len(epochs)==max_epochs and stale<patience}
