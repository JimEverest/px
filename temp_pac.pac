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
    
    // Example: Google uses proxy server 1
    if (host == "google.com" || host.endsWith(".google.com")) {
        return "PROXY 127.0.0.1:8080";
    }
    
    // Example: Amazon uses proxy server 2
    if (host == "amazon.com" || host.endsWith(".amazon.com")) {
        return "PROXY 127.0.0.1:8081";
    }
    
    // Default: use main proxy server
    return "PROXY 127.0.0.1:33210";
}