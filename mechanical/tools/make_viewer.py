#!/usr/bin/env python3
"""Wrap an STL in a single-file three.js viewer (drag to rotate, scroll to zoom).

Usage: make_viewer.py model.stl [viewer.html]
       (default output: model_view.html next to the STL; needs internet for three.js)
"""
import base64, pathlib, sys
if len(sys.argv) < 2:
    sys.exit(__doc__)
stl = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else stl.with_name(stl.stem + "_view.html")
b64 = base64.b64encode(stl.read_bytes()).decode()
html = """<!doctype html><html><head><meta charset="utf-8"><title>TITLE</title>
<style>html,body{margin:0;height:100%;background:#1e2329;color:#ccd;font:13px sans-serif;overflow:hidden}
#info{position:absolute;top:8px;left:10px;pointer-events:none}</style></head><body>
<div id="info">TITLE - drag to rotate, scroll to zoom, right-drag to pan</div>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const bin=Uint8Array.from(atob("B64"),c=>c.charCodeAt(0)).buffer;
const scene=new THREE.Scene();
const cam=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,1,2000);
const r=new THREE.WebGLRenderer({antialias:true});r.setSize(innerWidth,innerHeight);document.body.appendChild(r.domElement);
scene.add(new THREE.HemisphereLight(0xffffff,0x334455,0.9));
const d=new THREE.DirectionalLight(0xffffff,0.7);d.position.set(80,-120,200);scene.add(d);
const g=new THREE.STLLoader().parse(bin);g.computeVertexNormals();g.computeBoundingBox();
const c=new THREE.Vector3();g.boundingBox.getCenter(c);g.translate(-c.x,-c.y,-c.z);
scene.add(new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:0x5b8fd9,metalness:0.1,roughness:0.6})));
const grid=new THREE.GridHelper(200,20,0x445566,0x333a44);grid.rotation.x=Math.PI/2;grid.position.z=g.boundingBox.min.z-0.01;scene.add(grid);
cam.up.set(0,0,1);cam.position.set(90,-150,120);
const ctl=new THREE.OrbitControls(cam,r.domElement);ctl.update();
addEventListener('resize',()=>{cam.aspect=innerWidth/innerHeight;cam.updateProjectionMatrix();r.setSize(innerWidth,innerHeight)});
(function a(){requestAnimationFrame(a);ctl.update();r.render(scene,cam)})();
</script></body></html>""".replace("B64", b64)
html = html.replace("TITLE", stl.stem)
out.write_text(html)
print(f"wrote {out}")
