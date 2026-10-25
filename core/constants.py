# -*- coding: utf-8 -*-
"""全局常量：下载源、镜像映射、路径。"""

BMCLAPI = "https://bmclapi2.bangbang93.com"
MOJANG_META = "https://piston-meta.mojang.com"
MOJANG_LAUNCHERMETA = "https://launchermeta.mojang.com"
RESOURCES = "https://resources.download.minecraft.net"
LIBRARIES = "https://libraries.minecraft.net"
FORGE_MAVEN = "https://files.minecraftforge.net/maven"
FORGE_MAVEN2 = "https://maven.minecraftforge.net"
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases"
FABRIC_META = "https://meta.fabricmc.net"
FABRIC_MAVEN = "https://maven.fabricmc.net"
QUILT_META = "https://meta.quiltmc.org"
QUILT_MAVEN = "https://maven.quiltmc.org/repository/release"
TENCENT_MAVEN = "https://mirrors.cloud.tencent.com/nexus/repository/maven-public"

MANIFEST_BMCL = BMCLAPI + "/mc/game/version_manifest.json"
MANIFEST_OFFICIAL = MOJANG_META + "/mc/game/version_manifest.json"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MCBuilder/1.0"

# 需要按前缀替换到 BMCLAPI 的地址
BMCL_PREFIXES = [
    (MOJANG_META, BMCLAPI),
    (MOJANG_LAUNCHERMETA, BMCLAPI),
    ("https://piston-data.mojang.com", BMCLAPI),
    ("https://launcher.mojang.com", BMCLAPI),
    (LIBRARIES, BMCLAPI + "/libraries"),
    (RESOURCES, BMCLAPI + "/assets"),
    (FABRIC_META, BMCLAPI + "/fabric-meta"),
    (FABRIC_MAVEN, BMCLAPI + "/maven"),
    (FORGE_MAVEN, BMCLAPI + "/maven"),
    (FORGE_MAVEN2, BMCLAPI + "/maven"),
    (NEOFORGE_MAVEN, BMCLAPI + "/maven"),
    (QUILT_MAVEN, BMCLAPI + "/maven"),
    ("https://repo1.maven.org/maven2", TENCENT_MAVEN),
    ("https://repo.maven.apache.org/maven2", TENCENT_MAVEN),
]

# 这些域名优先走官方（BMCLAPI 的 maven 镜像不可靠，官方 CDN 反而更快）
OFFICIAL_FIRST_HOSTS = (
    "libraries.minecraft.net",
    "files.minecraftforge.net",
    "maven.minecraftforge.net",
    "maven.neoforged.net",
    "maven.fabricmc.net",
    "maven.quiltmc.org",
    "hmcl.glavo.site",
)

ASSET_HOST = "resources.download.minecraft.net"

# 已经压缩过的扩展名，打包时直接 store
STORED_EXTS = {
    ".jar", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".ogg", ".webp",
    ".mp3", ".mp4", ".lzma", ".gz", ".7z", ".rar",
}

SOURCE_AUTO = "auto"
SOURCE_BMCLAPI = "bmclapi"
SOURCE_OFFICIAL = "official"
