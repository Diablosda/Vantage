// Replace only the asset; object identity and all motion relationships remain intact.
export function replaceModelGeometry(target,model){
 if(!model?.modelSource||!Array.isArray(model.parts)||!model.parts.length)throw new Error('模型导入结果不完整');
 target.parts=model.parts;
 target.modelSource=model.modelSource;
}
