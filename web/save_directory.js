// Copy a completed local job to a directory explicitly chosen in the browser.
export async function copyJobToDirectory(directory,result,fetchFile=fetch){
 const name=result.directory.split(/[\\/]/).filter(Boolean).at(-1);
 if(!name||!result.downloads?.bundle)throw Error('保存任务缺少文件信息');
 const folder=await directory.getDirectoryHandle(name,{create:true});
 for(const url of Object.values(result.downloads)){
  const response=await fetchFile(url);if(!response.ok)throw Error('读取保存文件失败');
  const filename=decodeURIComponent(new URL(url,'http://localhost').pathname.split('/').at(-1));
  const file=await folder.getFileHandle(filename,{create:true}),writer=await file.createWritable();
  try{if(response.body?.pipeTo)await response.body.pipeTo(writer);else{await writer.write(await response.blob());await writer.close();}}
  catch(e){try{await writer.abort?.();}catch{}throw e;}
 }
 return name;
}
