"""Extract bounded reference-manual pages for offline recovery-entry review."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"Tools/ota"))
import p34_install_cost as host


def main():
    cli=host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode,"isolated root required")
    store=cli.Store(ROOT)
    out=store.checked(ROOT/".cache/p34-recovery-manual1")
    cli.require(not out.exists(),"preserve extraction")
    pages=(60,61,141,142,143,153,320,321,322,323,324,325,326,
           635,636,637,638,650,651,652,653,676,677,678,679)
    for number in pages:
        store.checked(out/("page-%04d.txt" % number))
    store.checked(out/"result.json")
    library=ROOT/".cache/p34-manual-tool1/lib"
    sys.path.insert(0,str(library))
    import pypdf
    cli.require(pypdf.__version__=="5.9.0","unexpected PDF parser")
    source=ROOT/"Doc/RM_AT32F435_437_V2.07_CH.pdf"
    reader=pypdf.PdfReader(source)
    outputs=[]
    for number in pages:
        data=reader.pages[number-1].extract_text()
        cli.require(bool(data.strip()),"empty page extraction")
        outputs.append(store.raw(out/("page-%04d.txt" % number),data.encode("utf-8")))
    inputs=[cli.record(Path(__file__)),cli.record(source)]
    inputs += [cli.record(p) for p in sorted((library/"pypdf").rglob("*.py"))]
    store.write(out/"result.json",dict(result="BOUNDED_REFERENCE_EXTRACTION",pages=list(pages),
        numbering="PDF pages, one-based",inputs=inputs,outputs=outputs,hardware=False))
    print("BOUNDED_REFERENCE_EXTRACTION pages="+str(len(pages)))


if __name__=="__main__":
    main()
