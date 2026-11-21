"""
Okunamayan (kapalı) CAD formatları için dışa aktarma rehberi.

SLDPRT, F3D gibi formatlar üreticiye özeldir ve açık bir kütüphaneyle okunamaz.
Kullanıcı dosyayı yüklediğinde program hangi programdan geldiğini uzantıdan
anlar ve o programda STL/STEP/DXF olarak nasıl dışa aktarılacağını gösterir.
"""

from typing import Final

# DEĞİŞTİRİLEBİLİR: Uzantı -> dosyanın geldiği program adı.
YEREL_FORMATLAR: Final[dict[str, str]] = {
    ".sldprt": "SolidWorks",
    ".sldasm": "SolidWorks",
    ".f3d": "Fusion 360",
    ".f3z": "Fusion 360",
    ".ipt": "Inventor",
    ".iam": "Inventor",
    ".catpart": "CATIA",
    ".prt": "Creo / NX",
    ".fcstd": "FreeCAD",
    ".skp": "SketchUp",
    ".blend": "Blender",
}

# DEĞİŞTİRİLEBİLİR: Program adı -> dışa aktarma adımları.
DISA_AKTARMA_ADIMLARI: Final[dict[str, list[str]]] = {
    "SolidWorks": [
        "Dosya > Farklı Kaydet menüsünü açın.",
        "Kayıt türü olarak STL (*.stl) seçin; STEP desteği eklendiğinde STEP AP214 de kullanılabilir.",
        "Seçenekler düğmesinden birimi milimetre yapın ve kaydedin.",
    ],
    "Fusion 360": [
        "Tarayıcıda parçaya sağ tıklayın ve 'Save as Mesh' seçin.",
        "Format olarak STL veya 3MF, birim olarak milimetre seçin.",
        "Levha şasi için: çizime (sketch) sağ tıklayıp 'Save as DXF' seçin.",
    ],
    "Inventor": [
        "Dosya > Dışa Aktar > CAD Formatı menüsünü açın.",
        "Dosya türü olarak STL seçin, Seçenekler'de birimi milimetre yapın.",
    ],
    "CATIA": [
        "File > Save As menüsünü açın.",
        "Kayıt türü olarak stl seçin.",
    ],
    "Creo / NX": [
        "Dosya > Farklı Kaydet / Dışa Aktar menüsünü açın.",
        "STL formatını ve milimetre birimini seçin.",
    ],
    "FreeCAD": [
        "Parçayı seçin, Dosya > Dışa Aktar menüsünü açın.",
        "Dosya türü olarak STL Mesh (*.stl) seçin.",
    ],
    "SketchUp": [
        "Dosya > Dışa Aktar > 3B Model menüsünü açın.",
        "Format olarak STL veya OBJ seçin, birimi milimetre yapın.",
    ],
    "Blender": [
        "File > Export > STL menüsünü açın.",
        "Ölçeğin milimetre ile uyumlu olduğundan emin olun (Scene Units).",
    ],
}

GENEL_TAVSIYE: Final[str] = (
    "Lütfen parçayı STL, OBJ, 3MF veya (levha şasi için) DXF olarak dışa aktarın."
)
STEP_BEKLEMEDE_MESAJI: Final[str] = (
    "STEP desteği henüz eklenmedi, sonraki sürümde gelecek. "
    "Şimdilik parçayı STL veya 3MF olarak dışa aktarıp yükleyin."
)
