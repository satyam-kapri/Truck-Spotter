/** Same-origin API calls: Vite proxies locally; Django handles these on Vercel. */
export async function api<T>(url:string, options?:RequestInit):Promise<T>{
  const response=await fetch(url,options);
  const mediaType=(response.headers.get('content-type')||'').split(';')[0].trim().toLowerCase();
  if(mediaType!=='application/json'&&!mediaType.endsWith('+json')){
    throw new Error(`API ${url} returned HTTP ${response.status} instead of JSON. The Django API may be missing or unavailable. Check the deployment's API routing and server logs.`);
  }
  let data;
  try{data=await response.json()}
  catch{throw new Error(`API ${url} returned invalid JSON (HTTP ${response.status}). Check the server logs.`)}
  if(!response.ok){
    const message=data?.error||data?.detail||validationMessage(data);
    throw new Error(typeof message==='string'&&message?message:`API request failed (HTTP ${response.status}).`);
  }
  return data as T;
}

function validationMessage(value:unknown):string{
  if(typeof value==='string')return value;
  if(Array.isArray(value))return value.map(validationMessage).filter(Boolean).join(' ');
  if(value&&typeof value==='object')return Object.entries(value).map(([key,item])=>`${key}: ${validationMessage(item)}`).join(' ');
  return '';
}
