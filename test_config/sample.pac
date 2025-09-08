// Sample PAC file for px-ui-client testing
// This PAC file demonstrates different proxy routing scenarios

function FindProxyForURL(url, host) {
    // Convert host to lowercase for case-insensitive matching
    host = host.toLowerCase();
    
    // Direct connection for local addresses
    if (isPlainHostName(host) ||
        shExpMatch(host, "localhost") ||
        shExpMatch(host, "127.0.0.1") ||
        shExpMatch(host, "*.local")) {
        return "DIRECT";
    }
    
    // Baidu.com and subdomains -> DIRECT connection
    if (shExpMatch(host, "*.baidu.com") || host == "baidu.com") {
        return "DIRECT";
    }
    
    // Google.com and subdomains -> proxy1
    if (shExpMatch(host, "*.google.com") || 
        shExpMatch(host, "*.googleapis.com") ||
        shExpMatch(host, "*.googleusercontent.com") ||
        host == "google.com") {
        return "PROXY proxy1.example.com:8080; DIRECT";
    }
    
    // Amazon.com and AWS services -> proxy2
    if (shExpMatch(host, "*.amazon.com") ||
        shExpMatch(host, "*.amazonaws.com") ||
        shExpMatch(host, "*.aws.amazon.com") ||
        host == "amazon.com") {
        return "PROXY proxy2.example.com:8080; DIRECT";
    }
    
    // Microsoft services -> proxy1 (same as Google)
    if (shExpMatch(host, "*.microsoft.com") ||
        shExpMatch(host, "*.microsoftonline.com") ||
        shExpMatch(host, "*.office.com") ||
        shExpMatch(host, "*.outlook.com")) {
        return "PROXY proxy1.example.com:8080; DIRECT";
    }
    
    // GitHub and development sites -> DIRECT
    if (shExpMatch(host, "*.github.com") ||
        shExpMatch(host, "*.stackoverflow.com") ||
        shExpMatch(host, "*.npmjs.com") ||
        shExpMatch(host, "*.pypi.org")) {
        return "DIRECT";
    }
    
    // Social media -> proxy2
    if (shExpMatch(host, "*.facebook.com") ||
        shExpMatch(host, "*.twitter.com") ||
        shExpMatch(host, "*.linkedin.com") ||
        shExpMatch(host, "*.instagram.com")) {
        return "PROXY proxy2.example.com:8080; DIRECT";
    }
    
    // Default: use upstream proxy with fallback to DIRECT
    return "PROXY 127.0.0.1:33210; DIRECT";
}