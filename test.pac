function FindProxyForURL(url, host) {
    // Default PAC configuration with example rules
    // Customize this function to define your proxy rules
    
    // Local network and localhost - direct connection
    if (isPlainHostName(host) || isInNet(host, "192.168.0.0", "255.255.0.0") || 
        isInNet(host, "10.0.0.0", "255.0.0.0") || isInNet(host, "127.0.0.0", "255.0.0.0")) {
        return "DIRECT";
    }
    
    // Example: Baidu uses direct connection
    if (host == "baidu.com" || host.endsWith(".baidu.com")) {
        return "DIRECT";
    }

    // Example: google uses proxy server 2
    if (host == "googleapis.com" || host.endsWith(".googleapis.com")) {
        return "PROXY googleapis-dev.gcp.cloud.hk.AZURE101:3128";
    }
    
    // Default: use main proxy server
    return "PROXY intpxy2.hk.AZURE101:8080";
}
