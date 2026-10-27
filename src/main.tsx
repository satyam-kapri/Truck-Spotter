import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import * as maplibregl from 'maplibre-gl';
import mapWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import {ArrowDown, ArrowRight, ArrowUpRight, Check, ChevronDown, ChevronRight, Clock3, CloudRain, Compass, Info, Layers3, LoaderCircle, MapPin, Navigation, Play, ShieldCheck, Snowflake, Truck, Wind, X, Pause, LocateFixed, ClipboardList, CloudSun, ChevronsUpDown, CircleHelp} from 'lucide-react';
import type {Analysis, Checkpoint, Corridor, Place, RiskLevel, Route} from './types';
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import './theme.css';

const COLORS:Record<RiskLevel,string>={Low:'#34cbb5',Moderate:'#e6c25b',High:'#f5a050',Severe:'#fb718b','No Travel':'#f34364',Unknown:'#9aa9bd'};
const LEVELS=Object.keys(COLORS) as RiskLevel[];
maplibregl.setWorkerUrl(mapWorkerUrl);
const ORIGIN:Place={label:'Chicago, Illinois',coordinates:[-87.6298,41.8781]};
const DEST:Place={label:'Nashville, Tennessee',coordinates:[-86.7816,36.1627]};
const duration=(s:number)=>`${Math.floor(s/3600)}h ${Math.round(s%3600/60)}m`;
const fmt=(v:number|null,d=0)=>v===null?'—':v.toLocaleString(undefined,{maximumFractionDigits:d});
const time=(v:string)=>new Date(v).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
async function api<T>(url:string, options?:RequestInit):Promise<T>{const r=await fetch(url,options); const data=await r.json();if(!r.ok)throw new Error(data.error||Object.values(data).flat().join(' ')||'Request failed.');return data;}

function PlaceInput({label,value,onChange,disabled,kind}:{label:string;value:Place;onChange:(v:Place)=>void;disabled:boolean;kind:string}){
 const [query,setQuery]=useState(value.label),[results,setResults]=useState<Place[]>([]),[error,setError]=useState('');
 const [resolved,setResolved]=useState(true);
 useEffect(()=>{if(value.label){setQuery(value.label);setResolved(true)}},[value]);
 useEffect(()=>{if(disabled||resolved||query.length<3){setResults([]);return}const controller=new AbortController();const id=setTimeout(()=>{api<Place[]>('/api/places?q='+encodeURIComponent(query),{signal:controller.signal}).then(setResults).catch(e=>{if(e.name!=='AbortError')setError('Place search unavailable. Try again.')})},400);return()=>{clearTimeout(id);controller.abort()}},[query,disabled,resolved]);
 return <div className="place-field"><label>{label}</label><div className="place-box"><span className={'place-dot '+kind}/><input aria-label={label} value={query} disabled={disabled} onChange={e=>{setQuery(e.target.value);setResolved(false);setError('');onChange({...value,label:'',coordinates:value.coordinates})}} placeholder="Search city or address"/>{resolved&&<Check size={14}/>}</div>{!resolved&&query.length>=3&&<div className="suggestions">{results.map((p,i)=><button type="button" key={i} onClick={()=>{onChange(p);setQuery(p.label);setResolved(true);setResults([])}}><MapPin size={14}/>{p.label}</button>)}{error&&<p>{error}</p>}{!error&&!results.length&&<p>Searching places…</p>}</div>}</div>
}

function App(){
 const [navSection,setNavSection]=useState('routes');
 const [mode,setMode]=useState<'demo'|'live'>('demo'),[origin,setOrigin]=useState(ORIGIN),[destination,setDestination]=useState(DEST);
 const [departure,setDeparture]=useState(()=>{const d=new Date();d.setMinutes(0,0,0);d.setHours(d.getHours()+1);return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)});
 const [load,setLoad]=useState('28000'),[spacing,setSpacing]=useState(25),[analysis,setAnalysis]=useState<Analysis|null>(null),[selected,setSelected]=useState('route-2');
 const [loading,setLoading]=useState(false),[error,setError]=useState(''),[corridor,setCorridor]=useState<Corridor|null>(null),[corridorError,setCorridorError]=useState(''),[corridorLoading,setCorridorLoading]=useState(false);
 const [hour,setHour]=useState(0),[layer,setLayer]=useState<'risk'|'wind'|'rain'|'snow'>('risk'),[showWeather,setShowWeather]=useState(true),[playing,setPlaying]=useState(false),[checkpoint,setCheckpoint]=useState<Checkpoint|null>(null),[showRules,setShowRules]=useState(false),[mobileTab,setMobileTab]=useState('trip');
 const mapNode=useRef<HTMLDivElement>(null), map=useRef<maplibregl.Map|null>(null),[mapReady,setMapReady]=useState(false),[mapError,setMapError]=useState(false);
 const analysisRef=useRef(analysis),selectedRef=useRef(selected);analysisRef.current=analysis;selectedRef.current=selected;
 const requestId=useRef(0);
 const current=analysis?.routes.find(r=>r.id===selected);

 async function analyzeTrip(){
   const id=++requestId.current;setLoading(true);setError('');setCheckpoint(null);setPlaying(false);
   try{
     const result=await api<Analysis>('/api/route-analyses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({origin,destination,departure:new Date(departure).toISOString(),load_lb:Number(load),spacing_miles:spacing,mode})});
     if(id!==requestId.current)return;
     setAnalysis(result);setSelected(result.recommended_id||result.routes[0].id);setCorridor(null);setHour(0);setCorridorError('');setCorridorLoading(true);
     api<Corridor>(`/api/route-analyses/${result.id}/corridor`).then(c=>{if(id===requestId.current)setCorridor(c)}).catch(e=>{if(id===requestId.current)setCorridorError(e.message)}).finally(()=>{if(id===requestId.current)setCorridorLoading(false)});
   }catch(e){if(id===requestId.current)setError((e as Error).message)}finally{if(id===requestId.current)setLoading(false)}
 }
 useEffect(()=>{void analyzeTrip()},[]);
 useEffect(()=>{if(!playing)return;const id=setInterval(()=>setHour(h=>(h+1)%49),650);return()=>clearInterval(id)},[playing]);
 useEffect(()=>{const id=requestAnimationFrame(()=>map.current?.resize());return()=>cancelAnimationFrame(id)},[mobileTab]);
 useEffect(()=>{if(!showRules)return;const close=(e:KeyboardEvent)=>{if(e.key==='Escape')setShowRules(false)};document.addEventListener('keydown',close);return()=>document.removeEventListener('keydown',close)},[showRules]);
 useEffect(()=>{
   if(!mapNode.current)return;
   try{
     const m=new maplibregl.Map({container:mapNode.current,style:'https://tiles.openfreemap.org/styles/dark',center:[-87.6,39.1],zoom:5.5,attributionControl:{compact:true}});
     map.current=m;
     m.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-left');
     m.on('load',()=>{
       // Keep the basemap in the reference's muted slate palette while retaining
       // geographic labels and the provider's source/attribution metadata.
       for(const baseLayer of m.getStyle().layers){
         const id=baseLayer.id.toLowerCase();
         if(baseLayer.type==='background')m.setPaintProperty(baseLayer.id,'background-color','#2e4048');
         if(baseLayer.type==='fill'){
           const color=id.includes('water')?'#506b76':id.includes('park')||id.includes('landcover')?'#30464a':id.includes('building')?'#3b5057':'#33464c';
           m.setPaintProperty(baseLayer.id,'fill-color',color);
         }
         if(baseLayer.type==='line'&&(id.includes('boundary')||id.includes('border'))){m.setPaintProperty(baseLayer.id,'line-color','#8a9ca3');m.setPaintProperty(baseLayer.id,'line-opacity',.45)}
         if(baseLayer.type==='line'&&(id.includes('road')||id.includes('highway')||id.includes('transportation'))){m.setPaintProperty(baseLayer.id,'line-color',id.includes('casing')?'#334950':'#84949c');m.setPaintProperty(baseLayer.id,'line-opacity',['interpolate',['linear'],['zoom'],4,.08,7,.18,11,.4,15,.7])}
         if(baseLayer.type==='line'&&id.includes('railway'))m.setPaintProperty(baseLayer.id,'line-opacity',.12);
         if(baseLayer.type==='symbol'&&baseLayer.layout?.['text-field']){m.setPaintProperty(baseLayer.id,'text-color','#bdcbd0');m.setPaintProperty(baseLayer.id,'text-halo-color','#30444d');m.setPaintProperty(baseLayer.id,'text-halo-width',1.2)}
       }
       m.addSource('corridor',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
       m.addLayer({id:'weather',type:'fill',source:'corridor',paint:{'fill-color':['get','color'],'fill-opacity':.23}});
       m.addSource('routes',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
       m.addLayer({id:'route-halo',type:'line',source:'routes',layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':'#071629','line-width':['case',['get','selected'],9,6],'line-opacity':.95}});
       m.addLayer({id:'route-lines',type:'line',source:'routes',layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':['get','color'],'line-width':['case',['get','selected'],5,3],'line-opacity':['case',['get','selected'],1,.55]}});
       m.addSource('points',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
       m.addLayer({id:'checkpoint-points',type:'circle',source:'points',paint:{'circle-radius':['case',['get','endpoint'],8,4],'circle-color':['get','color'],'circle-stroke-color':'#0b1b2d','circle-stroke-width':2}});
       m.on('click','checkpoint-points',e=>{const f=e.features?.[0];if(f){const p=analysisRef.current?.routes.find(r=>r.id===selectedRef.current)?.checkpoints.find(p=>p.id===Number(f.properties?.id));if(p)setCheckpoint(p)}});
       m.on('click','route-lines',e=>{const id=e.features?.[0]?.properties?.routeId;if(id){setSelected(id);setCheckpoint(null)}});
       for(const layer of ['route-lines','checkpoint-points']){m.on('mouseenter',layer,()=>{m.getCanvas().style.cursor='pointer'});m.on('mouseleave',layer,()=>{m.getCanvas().style.cursor=''})}
       setMapReady(true);
     });
     m.on('error',e=>{if(e.error?.message.includes('WebGL'))setMapError(true)});
     const observer=new ResizeObserver(()=>{m.resize();const a=analysisRef.current;if(a&&m.getContainer().clientWidth>0){const bounds=new maplibregl.LngLatBounds();a.routes.forEach(r=>r.coordinates.forEach(c=>bounds.extend(c)));m.fitBounds(bounds,{padding:{top:60,bottom:65,left:45,right:45},duration:0})}});
     observer.observe(mapNode.current);
     return()=>{observer.disconnect();m.remove();map.current=null};
   }catch{setMapError(true)}
 },[]);
 useEffect(()=>{
   const m=map.current;if(!m||!mapReady||!analysis)return;
   const features:GeoJSON.Feature[]=[];
   // Inactive routes first; selected route always draws on top.
   for(const r of [...analysis.routes].sort((a,b)=>Number(a.id===selected)-Number(b.id===selected))){
     if(r.id===selected){for(const interval of r.summary.intervals){const start=r.checkpoints[interval.from],end=r.checkpoints[interval.to];const line=routeSection(r,start,end);features.push({type:'Feature',geometry:{type:'LineString',coordinates:line},properties:{routeId:r.id,selected:true,color:COLORS[interval.level]}})}}
     else features.push({type:'Feature',geometry:{type:'LineString',coordinates:r.coordinates},properties:{routeId:r.id,selected:false,color:'#8e9cc8'}});
   }
   (m.getSource('routes') as maplibregl.GeoJSONSource).setData({type:'FeatureCollection',features});
   const r=analysis.routes.find(r=>r.id===selected)!;
   (m.getSource('points') as maplibregl.GeoJSONSource).setData({type:'FeatureCollection',features:r.checkpoints.map((p,i)=>({type:'Feature',geometry:{type:'Point',coordinates:p.coordinates},properties:{id:p.id,color:COLORS[p.risk.level],endpoint:i===0||i===r.checkpoints.length-1}}))});
 },[analysis,selected,mapReady]);
 useEffect(()=>{const m=map.current;if(!m||!mapReady||!analysis)return;const bounds=new maplibregl.LngLatBounds();analysis.routes.forEach(r=>r.coordinates.forEach(c=>bounds.extend(c)));m.fitBounds(bounds,{padding:{top:60,bottom:70,left:50,right:50},duration:900})},[analysis,mapReady]);
 useEffect(()=>{
   const m=map.current;if(!m||!mapReady)return;
   const features:GeoJSON.Feature[]=!corridor||!showWeather?[]:corridor.coordinates.map((c,i)=>{
     const value=corridor.frames[hour][i][layer];
     const score=value===null?null:layer==='risk'?value:layer==='wind'?value/15:layer==='rain'?value*6:value*2;
     const color=score===null?COLORS.Unknown:score<.8?'#76b6a2':score<1.6?'#d2cb6e':score<2.5?'#e9a65c':'#ce7280';
     const half=corridor.resolution_miles/69/2,dx=half/Math.cos(c[1]*Math.PI/180);
     return {type:'Feature',geometry:{type:'Polygon',coordinates:[[[c[0]-dx,c[1]-half],[c[0]+dx,c[1]-half],[c[0]+dx,c[1]+half],[c[0]-dx,c[1]+half],[c[0]-dx,c[1]-half]]]},properties:{color}};
   });
   (m.getSource('corridor') as maplibregl.GeoJSONSource).setData({type:'FeatureCollection',features});
 },[corridor,hour,layer,showWeather,mapReady]);
 function fitMap(){if(!map.current||!analysis)return;const bounds=new maplibregl.LngLatBounds();analysis.routes.forEach(r=>r.coordinates.forEach(c=>bounds.extend(c)));map.current.fitBounds(bounds,{padding:90,duration:700})}
 const dirty=analysis&&(analysis.mode!==mode||analysis.load_lb!==Number(load)||analysis.spacing_miles!==spacing||new Date(analysis.departure).getTime()!==new Date(departure).getTime()||mode==='live'&&(analysis.origin.label!==origin.label||analysis.destination.label!==destination.label));

 return <div className="app-shell">
  <aside className="navigation-rail"><a className="rail-brand" href="/" aria-label="Spotter home"><span className="brand-symbol"><i/><i/><i/></span><span><strong>Spotter TMS</strong><small>Weather-aware routing</small></span><ChevronsUpDown size={15}/></a><div className="rail-section-label">WORKSPACE</div><nav aria-label="Workspace"><button className={navSection==='routes'?'active':''} onClick={()=>{setNavSection('routes');setMobileTab('trip');document.querySelector('.sidebar')?.scrollTo({top:0,behavior:'smooth'})}}><ClipboardList size={20}/> Route planner</button><button className={navSection==='forecast'?'active':''} onClick={()=>{setNavSection('forecast');setMobileTab('map');document.getElementById('forecast')?.scrollIntoView({behavior:'smooth',block:'nearest'})}}><CloudSun size={20}/> Weather forecast</button><button onClick={()=>setShowRules(true)}><ShieldCheck size={20}/> Risk methodology</button></nav><div className="rail-bottom"><div className="rail-truck"><Truck size={22}/></div><strong>Built for the road.</strong><p>Weather and load insights<br/>for every mile ahead.</p><button onClick={()=>setShowRules(true)}><CircleHelp size={15}/> How Spotter works <ArrowUpRight size={13}/></button><div className="rail-version"><span/> SYSTEM READY <span>v1.0</span></div></div></aside>
  <header className="topbar"><div className="workspace-title"><span className="mobile-brand"><span className="brand-symbol"><i/><i/><i/></span></span><h1>Route planner</h1><span className="header-context"><Truck size={16}/> Weather-aware dispatch</span></div><nav><span className="header-data-status"><span/>{analysis?.mode==='live'?'Live':'Demo'}</span><button className="help-link" onClick={()=>setShowRules(true)}><Info size={16}/> How risk works</button><span className="avatar">SK</span></nav></header>
  <div className="mobile-tabs"><button className={mobileTab==='trip'?'active':''} onClick={()=>setMobileTab('trip')}>Plan & compare</button><button className={mobileTab==='map'?'active':''} onClick={()=>setMobileTab('map')}>Weather map</button></div>
  <main>
  <aside className={'sidebar '+(mobileTab==='trip'?'mobile-visible':'')}>
   <div className="planner-heading"><div className="eyebrow"><span/> TRIP DETAILS</div><h2>Plan your journey</h2><p>Compare weather at your estimated arrival.</p></div>
   <div className="mode-switch" aria-label="Data mode"><button onClick={()=>setMode('demo')} className={mode==='demo'?'active':''}><Compass size={14}/> Explore demo</button><button onClick={()=>setMode('live')} className={mode==='live'?'active':''}><span className="live-dot"/> Live journey</button></div>
   <form onSubmit={e=>{e.preventDefault();void analyzeTrip()}}>
    <div className="places"><PlaceInput label="FROM" value={origin} onChange={setOrigin} disabled={mode==='demo'} kind="origin"/><div className="place-connector"/><PlaceInput label="TO" value={destination} onChange={setDestination} disabled={mode==='demo'} kind="destination"/><button type="button" className="swap-button" aria-label="Swap origin and destination" disabled={mode==='demo'} onClick={()=>{setOrigin(destination);setDestination(origin)}}><ArrowDown size={16}/></button></div>
    <label className="field-label" htmlFor="departure">DEPARTURE <span>Browser local time</span></label><input id="departure" className="field-input" type="datetime-local" required value={departure} onChange={e=>setDeparture(e.target.value)}/>
    <div className="form-row"><div><label className="field-label" htmlFor="load">LOAD WEIGHT</label><div className="unit-input"><Truck size={16}/><input id="load" required type="number" min="0" max="200000" step="1" value={load} onChange={e=>setLoad(e.target.value)}/><span>lb</span></div></div><div><label className="field-label" htmlFor="spacing">CHECKPOINTS</label><div className="select-wrap"><select id="spacing" value={spacing} onChange={e=>setSpacing(Number(e.target.value))}>{[10,25,50].map(v=><option key={v} value={v}>Every {v} mi</option>)}</select><ChevronDown size={14}/></div></div></div>
    <button className="analyze-button" disabled={loading||mode==='live'&&(!origin.label||!destination.label)} type="submit">{loading?<><LoaderCircle className="spin" size={17}/> Assessing your journey…</>:<>Find the best route <ArrowRight size={18}/></>}</button>
    {error&&<p role="alert" className="error-message">{error}</p>}
   </form>
   <div className="results-heading"><h2>Your route options <span>{analysis?.routes.length||'—'}</span></h2><span>{loading?'Updating…':dirty?'Changes not applied':'Weather at arrival'}</span></div>
   <div className={'route-list '+(loading?'loading':'')}>
    {analysis?.routes.map((route,i)=>{const chosen=selected===route.id,recommended=analysis.recommended_id===route.id;const max=route.summary.blocked?'No Travel':!route.summary.complete?'Unknown':route.summary.miles_by_risk.Severe>0?'Severe':route.summary.miles_by_risk.High>0?'High':route.summary.miles_by_risk.Moderate>0?'Moderate':'Low';return <button key={route.id} className={'route-option '+(chosen?'selected':'')} onClick={()=>{setSelected(route.id);setCheckpoint(null)}}>
      <div className="route-option-top"><span className="route-number">0{i+1}</span><span className="route-name">{route.name}</span>{recommended?<span className="recommended"><ShieldCheck size={11}/> RECOMMENDED</span>:<span className="radio-dot">{chosen&&<i/>}</span>}</div>
      <div className="route-metrics"><strong>{duration(route.duration_seconds)}</strong><span>{fmt(route.distance_miles)} miles</span><span className="risk-label" style={{color:COLORS[max]}}><i style={{background:COLORS[max]}}/>{max==='Low'?'Low risk':max+' risk'}</span></div>
      <div className="risk-bar">{LEVELS.map(l=><span key={l} title={`${l}: ${route.summary.miles_by_risk[l].toFixed(1)} mi`} style={{width:`${route.summary.miles_by_risk[l]/route.distance_miles*100}%`,background:COLORS[l]}}/>)}</div>
      <div className="route-foot"><span>{route.checkpoints.length} checkpoints</span><span>{fmt(route.summary.miles_by_risk.High+route.summary.miles_by_risk.Severe,1)} high / severe mi</span></div>
     </button>})}
   </div>
   {analysis&&<div className="recommendation-note"><ShieldCheck size={18}/><div><strong>{analysis.recommended_id?'Why this route?':'No route recommended'}</strong><p>{analysis.reason}</p></div></div>}
   {current&&<details className="checkpoint-list"><summary>Inspect {current.checkpoints.length} checkpoints <ChevronDown size={13}/></summary><div className="checkpoint-list-heading"><span>MILE</span><span>ETA</span><span>RISK</span></div>{current.checkpoints.map(p=><button key={p.id} onClick={()=>{setCheckpoint(p);setMobileTab('map');map.current?.easeTo({center:p.coordinates,duration:600})}}><span>{fmt(p.mile,1)}</span><span>{time(p.eta)}</span><span style={{color:COLORS[p.risk.level]}}>{p.risk.level}</span><ChevronRight size={12}/></button>)}</details>}
   <div className="sidebar-foot"><ShieldCheck size={14}/> Assessment based on supplied weather rules.</div>
  </aside>
  <section className={'workspace '+(mobileTab==='map'?'mobile-visible':'')} aria-label="Route map and forecast">
   <div className="route-statusbar"><span className="status-chip eligible"><i/> ELIGIBLE ({analysis?.routes.filter(r=>r.summary.complete&&!r.summary.blocked).length??0})</span><span className="status-chip options">ROUTE OPTIONS ({analysis?.routes.length??0})</span><span className="status-chip blocked">NO TRAVEL ({analysis?.routes.filter(r=>r.summary.blocked).length??0})</span><span className="status-note"><ShieldCheck size={13}/> Arrival-time assessment</span></div>
   <div className="map-toolbar"><div className="journey-title"><Navigation size={17}/><strong>{analysis?.origin.label.split(',')[0]||'Your origin'}</strong><ArrowRight size={15}/><strong>{analysis?.destination.label.split(',')[0]||'Destination'}</strong></div><span className={'data-badge '+(analysis?.mode==='live'?'live':'')}>{analysis?.mode==='live'?<><span/> LIVE FORECAST</>:<><span/> ILLUSTRATIVE DEMO</>}</span></div>
   {analysis?.mode==='live'&&<div className="analysis-warnings" role="status"><Info size={12}/><span>{analysis.warnings.join(' ')}</span></div>}
   <div className="map-area"><div className="map-canvas" ref={mapNode}/>{mapError&&<div className="map-fallback">Map rendering is unavailable on this device. Route details remain available in the comparison panel.</div>}
    <div className="map-top-line"><span className="map-view-label"><span/> {current?.name||'Route overview'}</span><button onClick={()=>setShowWeather(v=>!v)} className={'layer-button '+(showWeather?'enabled':'')}><Layers3 size={15}/><span>Weather layer</span><span className="toggle"><i/></span></button></div>
    <div className="map-legend"><span>ROUTE RISK</span>{LEVELS.slice(0,5).map(l=><div key={l}><i style={{background:COLORS[l]}}/>{l}</div>)}<button onClick={()=>setShowRules(true)} aria-label="Risk definitions"><Info size={14}/></button></div>
    <button className="fit-map" onClick={fitMap} aria-label="Fit all routes"><LocateFixed size={18}/></button>
    {current&&<div className="map-trip-summary"><div className="summary-icon"><Navigation size={21}/></div><div><small>SELECTED JOURNEY</small><strong>{duration(current.duration_seconds)} <span>· {fmt(current.distance_miles)} mi</span></strong></div><div className="arrival"><small>ARRIVAL</small><strong>{time(current.checkpoints.at(-1)!.eta)}</strong></div></div>}
    {checkpoint&&<div className="checkpoint-panel"><div className="checkpoint-title"><div><small>CHECKPOINT {checkpoint.id+1} · MILE {fmt(checkpoint.mile)}</small><h3 style={{color:COLORS[checkpoint.risk.level]}}>{checkpoint.risk.level} risk</h3></div><button onClick={()=>setCheckpoint(null)} aria-label="Close checkpoint"><X size={17}/></button></div><div className="checkpoint-weather"><span><Wind size={18}/><strong>{fmt(checkpoint.weather.wind_mph,1)}</strong> mph</span><span><CloudRain size={18}/><strong>{fmt(checkpoint.weather.rain_in_hr,2)}</strong> in/hr</span><span><Snowflake size={18}/><strong>{fmt(checkpoint.weather.snow_in_hr,2)}</strong> in/hr</span></div><p><Clock3 size={13}/> Estimated arrival {time(checkpoint.eta)}</p>{checkpoint.risk.reasons.map((reason,i)=><p key={i}>{reason}</p>)}</div>}
    {loading&&<div className="map-loading"><LoaderCircle className="spin" size={18}/> Matching forecasts to arrival times</div>}
   </div>
   <section className="forecast" id="forecast"><div className="forecast-heading"><div><span className="eyebrow">48-HOUR OUTLOOK</span><h2>Corridor forecast</h2></div><div className="weather-tabs">{([{id:'risk',label:'Combined risk',icon:ShieldCheck},{id:'wind',label:'Wind',icon:Wind},{id:'rain',label:'Rain',icon:CloudRain},{id:'snow',label:'Snow',icon:Snowflake}] as const).map(t=><button key={t.id} className={layer===t.id?'active':''} onClick={()=>setLayer(t.id)}><t.icon size={14}/>{t.label}</button>)}</div></div>
    <div className="timeline"><button className="play-button" disabled={!corridor} aria-label={playing?'Pause forecast':'Play forecast'} onClick={()=>setPlaying(v=>!v)}>{playing?<Pause size={16}/>:<Play size={16}/>}</button><div className="slider-area"><div className="slider-labels"><span>Departure</span><strong>{corridor?new Date(corridor.times[hour]).toLocaleString([],{weekday:'short',hour:'numeric',minute:'2-digit'}):'Loading forecast'} <span>+{hour}h</span></strong><span>+48 hours</span></div><input aria-label="Forecast hours after departure" type="range" min="0" max="48" value={hour} disabled={!corridor} onChange={e=>{setHour(Number(e.target.value));setPlaying(false)}} style={{'--progress':`${hour/48*100}%`} as React.CSSProperties}/><div className="slider-ticks">{[0,6,12,18,24,30,36,42,48].map(h=><button key={h} disabled={!corridor} onClick={()=>setHour(h)}>{h===0?'0h':`+${h}h`}</button>)}</div></div></div>
    <div className="forecast-foot"><span>{corridorLoading?<><LoaderCircle className="spin" size={12}/> Loading corridor forecasts…</>:corridorError?<span className="forecast-error">{corridorError}</span>:<><Info size={12}/> {corridor?`${corridor.width_miles}-mile corridor · ${fmt(corridor.resolution_miles)} mi grid`:'Corridor forecast unavailable'} · {layer==='wind'?'Wind intensity (mph)':layer==='rain'?'Rain intensity (in/hr)':layer==='snow'?'Snowfall intensity (in/hr)':'Load-adjusted weather risk'}</>}</span><span className="heat-scale"><i/> Lower <b/> Higher</span></div>
   </section>
   <footer className="workspace-foot"><span>{analysis?.mode==='demo'?'Demo uses synthetic weather and illustrative route corridors.':'Forecast: Open-Meteo · Routing: '+(current?.provider||'—')}</span><button onClick={()=>setShowRules(true)}>Method & limitations <ArrowUpRight size={12}/></button></footer>
  </section>
  </main>
  {showRules&&<div className="modal-backdrop" onClick={()=>setShowRules(false)}><section className="rules-modal" role="dialog" aria-modal="true" aria-labelledby="rules-title" onClick={e=>e.stopPropagation()}><button className="modal-close" onClick={()=>setShowRules(false)} aria-label="Close risk rules"><X size={20}/></button><div className="eyebrow">THE METHOD</div><h2 id="rules-title">A recommendation you can inspect.</h2><p>We assess weather at each checkpoint’s estimated arrival time. The highest weather or load risk wins.</p><div className="rules-table"><table><thead><tr><th>Condition</th><th>Low</th><th>Moderate</th><th>High</th><th>Severe</th><th>No Travel</th></tr></thead><tbody><tr><th>Wind · mph</th><td>&lt;25</td><td>25–&lt;35</td><td>35–&lt;45</td><td>45–&lt;55</td><td>≥55</td></tr><tr><th>Rain · in/hr</th><td>&lt;.10</td><td>.10–&lt;.25</td><td>.25–&lt;.50</td><td>.50–1.00</td><td>&gt;1.00</td></tr><tr><th>Snow · in/hr</th><td>&lt;.5</td><td>.5–&lt;1</td><td>1–&lt;2</td><td>2–3</td><td>&gt;3</td></tr></tbody></table></div><h3>Load changes the assessment</h3><p>45–&lt;55 mph wind with more than 30,000 lb means No Travel. 35–&lt;45 mph with more than 40,000 lb means Severe. At 55 mph, all loads are No Travel.</p><h3>How we choose</h3><p>Exclude No Travel and incomplete routes. Then compare, in order: fewest Severe miles, fewest High miles, lowest distance-weighted risk, shortest driving time. Each interval uses the more restrictive endpoint risk.</p><h3>Two views of time</h3><p>Route colors use arrival-time weather. The slider shows the whole corridor at one selected instant, from departure to +48 hours. It does not change the recommendation.</p><p className="method-note">Driving times exclude breaks. Automotive routing does not assess truck clearances or axle limits. Sampled forecasts may miss hazards between checkpoints. The demo uses synthetic weather and illustrative corridors. Live mode uses third-party forecasts; missing data stays Unknown.</p><button className="analyze-button" onClick={()=>setShowRules(false)}>Back to the journey <ArrowRight size={17}/></button></section></div>}
 </div>
}

function routeSection(r:Route,a:Checkpoint,b:Checkpoint):[number,number][]{
 return [a.coordinates,...r.coordinates.slice(a.segment_index+1,b.segment_index+1),b.coordinates];
}

createRoot(document.getElementById('root')!).render(<App/>);
