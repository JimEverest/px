// Complex PAC file for advanced testing scenarios
function FindProxyForURL(url, host) {
    var resolved_ip = dnsResolve(host);
    
    // Local network ranges - go direct
    if (isInNet(resolved_ip, "10.0.0.0", "255.0.0.0") ||
        isInNet(resolved_ip, "172.16.0.0", "255.240.0.0") ||
        isInNet(resolved_ip, "192.168.0.0", "255.255.0.0") ||
        isInNet(resolved_ip, "127.0.0.0", "255.0.0.0")) {
        return "DIRECT";
    }
    
    // Time-based routing (office hours use different proxy)
    var now = new Date();
    var hour = now.getHours();
    var isOfficeHours = (hour >= 9 && hour <= 17);
    
    // URL-based routing with time consideration
    if (shExpMatch(url, "https://*")) {
        if (isOfficeHours) {
            return "PROXY office-proxy.example.com:8080; PROXY backup-proxy.example.com:8080; DIRECT";
        } else {
            return "PROXY night-proxy.example.com:8080; DIRECT";
        }
    }
    
    // HTTP traffic
    if (shExpMatch(url, "http://*")) {
        // Block certain domains during office hours
        if (isOfficeHours && (shExpMatch(host, "*.facebook.com") || 
                             shExpMatch(host, "*.twitter.com") ||
                             shExpMatch(host, "*.youtube.com"))) {
            return "PROXY blocked.example.com:8080";
        }
        return "PROXY http-proxy.example.com:8080; DIRECT";
    }
    
    // FTP traffic
    if (shExpMatch(url, "ftp://*")) {
        return "PROXY ftp-proxy.example.com:8080; DIRECT";
    }
    
    // Default fallback
    return "PROXY 127.0.0.1:33210; DIRECT";
}