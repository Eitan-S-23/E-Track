"""Write-once host log rotation; qualification only, not mutation admission."""


class Segments:
    def __init__(self, paths, switch, record, emit):
        if len(paths) != 6 or len(set(paths)) != 6:
            raise ValueError('six distinct preflighted log paths required')
        self.paths = tuple(paths)
        self.switch, self.record, self.emit = switch, record, emit
        self.index = 0
        self.sealed = []
        self.error = None
        self.finished = False

    def check(self):
        if self.error is not None or self.finished:
            raise ValueError('log segmentation consumed/failed')

    def seal(self):
        value = self.record(self.paths[self.index])
        if value['path'] != str(self.paths[self.index]) or not 0 < value['bytes'] <= 16*1024*1024:
            raise ValueError('empty/oversize/misdirected SDK log segment')
        self.sealed.append(value)

    def rotate(self):
        try:
            self.check()
            if self.index >= 5:
                raise ValueError('fixed rotation count exhausted')
            old = self.index
            self.emit('sdk-log-switch-attempt', old=old, new=old+1)
            self.switch(self.paths[old+1])
            self.emit('sdk-log-switch-returned', old=old, new=old+1)
            self.seal()
            self.index += 1
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise

    def finish(self, native_closed):
        try:
            self.check()
            if native_closed is not True or self.index != 5:
                raise ValueError('five rotations and native close required')
            self.seal()
            if self.sealed != [self.record(path) for path in self.paths]:
                raise ValueError('sealed SDK log changed')
            self.finished = True
            return list(self.sealed)
        except BaseException as error:
            if self.error is None:
                self.error = type(error).__name__+': '+str(error)
            raise


def rotation_events(rows):
    actual = [(row['event'],row.get('old'),row.get('new')) for row in rows
              if row['event'].startswith('sdk-log-switch-')]
    expected = [(event,i,i+1) for i in range(5)
                for event in ('sdk-log-switch-attempt','sdk-log-switch-returned')]
    if actual != expected:
        raise ValueError('missing/extra/reordered native log rotation')


def checked_records(paths, records, record):
    if len(paths) != 6 or records != [record(path) for path in paths]:
        raise ValueError('raw segment order/content changed')
    if any(not 0 < item['bytes'] <= 16*1024*1024 for item in records):
        raise ValueError('empty/oversize segment')


def checked_lines(streams, rows):
    """Bind real SDK segment boundaries to complete journal frames and AP state."""
    from p34_nor_audit import WREG, RREG, VALUE, RETURN
    rows=list(rows)
    rotation_events(rows)
    expected=[0]*6
    states=[]
    segment=0
    frame=None
    for row in rows:
        event=row['event']
        if event=='recovery-chunk-read-attempt':
            if frame is not None: raise ValueError('overlapping journal frame')
            frame=row
        elif event=='recovery-chunk-read-returned':
            if frame is None or frame['address']!=row['address'] or frame['bytes']*2!=len(row['data_hex']):
                raise ValueError('unpaired journal frame')
            expected[segment]+=frame['bytes']//4
            frame=None
        elif event=='recovery-word-read': expected[segment]+=1
        elif event=='sdk-log-switch-attempt':
            if frame is not None: raise ValueError('log rotation inside a journal frame')
            segment+=1
        elif event=='sdk-log-state': states.append(row)
    if frame is not None or len(states)!=5 or len(streams)!=6:
        raise ValueError('incomplete rotation frame/state sequence')
    bank=0
    def state_ops(values):
        if len(values)!=3: raise ValueError('three boundary registers required')
        return [('read','DP',1,values[0]),('read','AP',0,values[1]),('read','AP',1,values[2])]
    for index,stream in enumerate(streams):
        pending=None
        first=[]
        tail=[]
        words=0
        for line in stream:
            wr,rd,val,ret=WREG.search(line),RREG.search(line),VALUE.search(line),RETURN.search(line)
            if wr:
                if pending is not None: raise ValueError('overlapping native boundary call')
                pending=['write',wr[1],int(wr[2],16),int(wr[3],16)]
                if pending[1:3]==['DP',2]: bank=pending[3]
            elif rd:
                if pending is not None: raise ValueError('overlapping native boundary call')
                pending=['read',rd[1],int(rd[2],16),None]
            elif val and pending and pending[0]=='read':
                if pending[3] is not None: raise ValueError('duplicate native read value')
                pending[3]=int(val[1],16)
                if pending[1:3]==['AP',3] and bank==0: words+=1
            elif ret and pending:
                if pending[3] is None or int(ret[1])<0: raise ValueError('failed/incomplete native boundary call')
                operation=tuple(pending)
                if len(first)<3: first.append(operation)
                tail=(tail+[operation])[-3:]
                pending=None
            yield line
        if pending is not None or words!=expected[index]:
            raise ValueError('native call/frame crosses declared segment boundary')
        if index and first!=state_ops(states[index-1]['after']):
            raise ValueError('SDK segment head differs from post-switch AP state')
        if index<5 and tail!=state_ops(states[index]['before']):
            raise ValueError('SDK segment tail differs from pre-switch AP state')
