// Apply a neutral fallback only to glTF primitives that have neither a
// material nor vertex colors. Authored materials and colors stay untouched.
export function applyModelMaterialFallback(gltf){
 const cache=new WeakMap(),parser=gltf.parser;
 gltf.scene.traverse(mesh=>{
  if(!mesh.isMesh||mesh.geometry?.attributes?.color)return;
  const ref=parser.associations.get(mesh);
  if(ref?.meshes===undefined||ref?.primitives===undefined)return;
  const primitive=parser.json.meshes?.[ref.meshes]?.primitives?.[ref.primitives];
  if(!primitive||primitive.material!==undefined||!mesh.material||Array.isArray(mesh.material))return;
  const original=mesh.material;let fallback=cache.get(original);
  if(!fallback){fallback=original.clone();fallback.color.setHex(0xb7bdc4);fallback.metalness=0;fallback.roughness=.85;cache.set(original,fallback);}
  mesh.material=fallback;
 });
 return gltf;
}
