"""Build a host-only confirmation DLL and test exact eight-page model transport."""
import argparse
import ctypes as c
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_install_cost as host

cli=host.cli
U8=c.c_uint8
PAIR=(U8*64)*2
class Plan(c.Structure):_fields_=[('operation',U8*16),('before',PAIR)]
class Request(c.Structure):
    _fields_=[('boot',c.POINTER(U8)),('image',c.POINTER(U8)),('boot_length',c.c_size_t),
              ('image_length',c.c_size_t),('operation',U8*16)]
class Result(c.Structure):
    _fields_=[('before',PAIR),('after',PAIR),('write_attempts',c.c_uint),('transaction_status',c.c_int),
              ('before_read',c.c_int),('after_read',c.c_int),('active',c.c_int)]
WRITE=c.CFUNCTYPE(c.c_int,U8,c.POINTER(U8),c.c_uint16)
READ=c.CFUNCTYPE(c.c_int,U8,c.POINTER(U8),c.c_uint16)
class HAL(c.Structure):_fields_=[('write_buffer',WRITE),('read_buffer',READ)]


def bind(path):
    dll=c.CDLL(str(path));dll.rc_host_size.argtypes=[c.c_uint];dll.rc_host_size.restype=c.c_uint
    cli.require([dll.rc_host_size(i) for i in range(4)]==[c.sizeof(t) for t in (Plan,Request,Result,HAL)],'host ABI mismatch')
    fn=dll.rc_host_confirm;fn.argtypes=[c.POINTER(t) for t in (Plan,Request,HAL,Result)];fn.restype=c.c_int
    return dll,fn


def confirm(fn, before, boot, image, read, write):
    cli.require(type(before) is bytes and len(before)==128,'exact model preimage pair')
    plan=Plan();c.memmove(c.addressof(plan)+Plan.before.offset,before,128)
    plan.operation[:]=b'HOST-PAGE-ONLY-1'
    boot_buffer=(U8*len(boot)).from_buffer_copy(boot);image_buffer=(U8*len(image)).from_buffer_copy(image)
    request=Request(boot_buffer,image_buffer,len(boot),len(image),plan.operation)
    errors=[]
    def read_cb(address,dst,size):
        try:
            data=read(address,size)
            cli.require(type(data) is bytes and len(data)==size,'model read length')
            c.memmove(dst,data,size);return 0
        except BaseException as error:errors.append(type(error).__name__+': '+str(error));return -1
    def write_cb(address,src,size):
        try:return write(address,c.string_at(src,size))
        except BaseException as error:errors.append(type(error).__name__+': '+str(error));return -1
    hal=HAL(WRITE(write_cb),READ(read_cb));result=Result()
    status=fn(c.byref(plan),c.byref(request),c.byref(hal),c.byref(result))
    return dict(status=status,result=result,callback_errors=errors)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated root required')
    store=cli.Store(ROOT);out=store.checked(args.output_dir);cli.require(not out.exists(),'preserve host page model')
    boot=ROOT/'.cache/p34-bc-target/f';app=ROOT/'.cache/p34-early-usb-r2/f';component=ROOT/'Tools/ota/recovery_confirm'
    sources=[component/'confirm.c',component/'host_binding.c']
    sources += [boot/'boot/src'/n for n in ('boot_state_machine.c','boot_fw_header.c','boot_crc32.c','boot_sha256.c','boot_slot.c')]
    sources += [boot/'Libraries/EEPROM/eeprom_bcb.c']
    inputs=sources+[component/'confirm.h',component/'page_port.py',Path(__file__),ROOT/'tests/boot/test_p34_confirm_page.py',
        ROOT/'.cache/p34-host-nor-rebuild1/bcb-before.bin',ROOT/'.cache/p34-native-acquire1/boot-readback.bin',
        ROOT/'.cache/p34-native-image1/app-readback.bin',ROOT/'.cache/p34-recovery-sources1/r2-a.bin']
    boot_header=boot/'Libraries/EEPROM/eeprom_bcb.h';app_header=app/'Libraries/EEPROM/eeprom_bcb.h'
    cli.require(boot_header.read_bytes().replace(b'\r\n',b'\n')==app_header.read_bytes().replace(b'\r\n',b'\n'),
                'Boot/App BCB headers differ; host ABI needs explicit reconciliation')
    inputs+=list((boot/'boot/include').glob('*.h'))+list((app/'Libraries/OTA').glob('*.h'))+[app_header,boot_header]
    for n in ('confirm.dll','compile.log','compile.json','tests.log','tests.json','result.json'):store.checked(out/n)
    for p in inputs:store.checked(out/'source'/p.relative_to(ROOT))
    records=[cli.record(p) for p in inputs];env=host.environment(store,out)
    for p in inputs:store.raw(out/'source'/p.relative_to(ROOT),p.read_bytes())
    cc=Path('D:/install/mingw64/bin/gcc.exe')
    host.command(store,out,'compile',[cc,'-std=c99','-O2','-Wall','-Wextra','-Werror','-DRR_CONFIRM_HOST_ONLY','-shared',
        '-I'+str(component),'-I'+str(boot/'boot/include'),'-I'+str(app/'Libraries'),*sources,'-o',out/'confirm.dll'],env,90)
    env['P34_CONFIRM_DLL']=str(out/'confirm.dll')
    log=host.command(store,out,'tests',[sys.executable,'-I','-S','-B','-X','utf8',ROOT/'tests/boot/test_p34_confirm_page.py','-v'],env,180)
    match=re.search(rb'Ran (\d+) tests? in .*\r?\n\r?\nOK\b',log)
    cli.require(match and records==[cli.record(p) for p in inputs],'tests/source drift')
    store.write(out/'result.json',dict(result='HOST_ONLY_CONFIRM_PAGE_MODEL_PASS',tests=int(match[1]),inputs=records,
        compiler=cli.record(cc),dll=cli.record(out/'confirm.dll'),hardware=False,device_entry=False,
        scope='Unchanged confirmation core, actual observed preimage as fixture, hypothetical R2 internal image only'))
    print('HOST_ONLY_CONFIRM_PAGE_MODEL_PASS',int(match[1]))


if __name__=='__main__':main()
