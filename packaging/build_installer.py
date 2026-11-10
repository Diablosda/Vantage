"""Build an offline installer from approved source and clean upstream archives."""
import argparse,hashlib,json,re,shutil,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def copytree(source,target):
 shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo','portable'),dirs_exist_ok=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--refresh-app',action='store_true');args=parser.parse_args();work=args.work.resolve()
 version=re.search(r"APP_VERSION='([^']+)'",(ROOT/'server.py').read_text(encoding='utf-8')).group(1)
 components=json.loads((ROOT/'packaging/components.json').read_text(encoding='utf-8'))
 for key,name in [('blender','blender.zip'),('ffmpeg','ffmpeg.zip'),('nsis','nsis.zip')]:assert hashlib.sha256((work/name).read_bytes()).hexdigest()==components[key]['sha256'],name
 stage=work/'stage'
 if stage.exists() and not (args.refresh_app and (stage/'.vantage-installation').is_file()):raise SystemExit('Stage already exists: choose a fresh build work directory')
 stage.mkdir(parents=True,exist_ok=True)
 for folder in ['ai_previs','backend','web','launcher']:copytree(ROOT/folder,stage/folder)
 for name in ['server.py','Vantage.exe','Vantage.Dialogs.exe','Vantage.cmd','README.md','产品说明.md','THIRD_PARTY.md']:shutil.copy2(ROOT/name,stage/name)
 copytree(next((work/'blender').iterdir()),stage/'runtime'/'blender')
 ffmpeg=next((work/'ffmpeg').iterdir());(stage/'runtime'/'ffmpeg').mkdir(parents=True,exist_ok=True)
 for src,name in [(ffmpeg/'bin'/'ffmpeg.exe','ffmpeg.exe'),(ffmpeg/'LICENSE','LICENSE'),(ffmpeg/'README.txt','README.txt')]:shutil.copy2(src,stage/'runtime'/'ffmpeg'/name)
 # Confirm the runtime has no user-created data or loose local machine paths.
 for name in ['model','场景','动作','projects','.runtime','.git']:assert not (stage/name).exists(),name
 assert not (stage/'runtime'/'blender'/'portable').exists()
 for path in stage.rglob('*'):
  if path.is_file() and path.relative_to(stage).parts[0]!='runtime' and path.suffix in ('.py','.cs','.js','.md','.cmd'):
   text=path.read_text(encoding='utf-8-sig')
   assert not re.search(r'[A-Za-z]:[/\\]+Users[/\\]+[^/\\\s]+',text),path.relative_to(stage)
 (stage/'.vantage-installation').write_text('Vantage '+version,encoding='utf-8')
 files=[{'path':p.relative_to(stage).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(stage.rglob('*')) if p.is_file()]
 (ROOT/'dist').mkdir(exist_ok=True);manifest=ROOT/'dist'/('Vantage-'+version+'-manifest.json');manifest.write_text(json.dumps({'version':version,'files':files},ensure_ascii=False,indent=2),encoding='utf-8')
 uninstall=work/'uninstall-files.nsh'
 lines=['Delete "$INSTDIR\\'+p['path'].replace('/','\\')+'"' for p in files]
 directories=sorted((p for p in stage.rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True)
 lines += ['RMDir "$INSTDIR\\'+p.relative_to(stage).as_posix().replace('/','\\')+'"' for p in directories]
 uninstall.write_text('\n'.join(lines),encoding='utf-8-sig')
 compiler=next((work/'nsis').rglob('makensis.exe'));output=ROOT/'dist'/('Vantage-'+version+'-Setup.exe')
 subprocess.run([str(compiler),'/V2','/DVERSION='+version,'/DSTAGE='+str(stage),'/DUNINSTALL_LIST='+str(uninstall),'/DOUTPUT='+str(output),str(ROOT/'packaging'/'Vantage.nsi')],check=True)
 print(output,flush=True)
if __name__=='__main__':main()
