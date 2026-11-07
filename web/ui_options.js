const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function options(values,selected){return Object.entries(values).map(([key,label])=>`<option value="${escapeHTML(key)}" ${String(key)===String(selected)?'selected':''}>${escapeHTML(label)}</option>`).join('');}
